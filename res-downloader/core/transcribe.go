package core

import (
	"bufio"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"res-downloader/core/shared"
	"runtime"
	"strconv"
	"strings"
	"sync"
)

// Transcriber 调用本地 Python (faster-whisper) 把已下载的音视频转录为 srt/txt 字幕。
// 通过单一 worker 串行处理任务：一次只跑一个 python 进程，避免多个进程同时加载语音
// 模型把内存/显存挤爆导致整机卡死。
type Transcriber struct {
	tasks sync.Map // id -> *exec.Cmd
	jobs  chan transcribeJob
}

type transcribeJob struct {
	mediaInfo shared.MediaInfo
	format    string
	language  string
}

func initTranscribe() *Transcriber {
	if transcribeOnce == nil {
		transcribeOnce = &Transcriber{
			jobs: make(chan transcribeJob, 256),
		}
		go transcribeOnce.worker()
	}
	return transcribeOnce
}

// worker 串行消费队列，保证同一时刻只有一个转录进程在跑。
func (tr *Transcriber) worker() {
	for j := range tr.jobs {
		tr.runJob(j.mediaInfo, j.format, j.language)
	}
}

// resolveScript 找到 transcribe.py 的绝对路径。
// 优先用配置里的 TranscribeScript，否则在可执行文件目录、当前工作目录及其上级里找 python/transcribe.py。
func (tr *Transcriber) resolveScript() (string, error) {
	if globalConfig.TranscribeScript != "" {
		if _, err := os.Stat(globalConfig.TranscribeScript); err == nil {
			return globalConfig.TranscribeScript, nil
		}
	}

	var roots []string
	if exe, err := os.Executable(); err == nil {
		roots = append(roots, filepath.Dir(exe))
	}
	if cwd, err := os.Getwd(); err == nil {
		roots = append(roots, cwd, filepath.Dir(cwd))
	}

	for _, root := range roots {
		p := filepath.Join(root, "python", "transcribe.py")
		if _, err := os.Stat(p); err == nil {
			return p, nil
		}
	}
	return "", errors.New("找不到转录引擎：便携版请确认 transcriber 文件夹与程序在同一目录；开发版请装好 Python 或在设置里配置“转录脚本路径”")
}

// resolveRunner 决定如何调用转录器，返回 (可执行文件, 前置参数, 工作目录)。
//  1. 优先用同目录打包好的独立转录器 transcriber/transcribe[.exe]（自带 Python，无需配环境，用于发布版）；
//  2. 否则回退到 "python transcribe.py"（开发模式，不受影响）。
//
// 工作目录约定为转录器所在目录，模型默认就放在该目录的 models/ 子目录下，两种模式统一。
func (tr *Transcriber) resolveRunner() (exe string, baseArgs []string, dir string, err error) {
	name := "transcribe"
	if runtime.GOOS == "windows" {
		name = "transcribe.exe"
	}
	var roots []string
	if ex, e := os.Executable(); e == nil {
		roots = append(roots, filepath.Dir(ex))
	}
	if cwd, e := os.Getwd(); e == nil {
		roots = append(roots, cwd, filepath.Dir(cwd))
	}
	for _, root := range roots {
		p := filepath.Join(root, "transcriber", name)
		if _, e := os.Stat(p); e == nil {
			return p, nil, filepath.Dir(p), nil
		}
	}

	// 回退：python 脚本
	script, e := tr.resolveScript()
	if e != nil {
		return "", nil, "", e
	}
	python := globalConfig.PythonPath
	if python == "" {
		python = "python"
	}
	return python, []string{script}, filepath.Dir(script), nil
}

// transcribe 把一个转录请求快速入队（不阻塞），实际转录由单一 worker 串行执行。
func (tr *Transcriber) transcribe(mediaInfo shared.MediaInfo, format, language string) {
	filePath := mediaInfo.SavePath
	if filePath == "" {
		tr.emit(mediaInfo, "无文件路径", shared.DownloadStatusError)
		return
	}
	if _, err := os.Stat(filePath); err != nil {
		tr.emit(mediaInfo, "文件不存在: "+filePath, shared.DownloadStatusError)
		return
	}
	// 用与实际执行相同的解析逻辑做校验（优先打包引擎，其次 python 脚本）
	if _, _, _, err := tr.resolveRunner(); err != nil {
		tr.emit(mediaInfo, err.Error(), shared.DownloadStatusError)
		return
	}

	// 入队，先给前端一个"排队中"反馈
	tr.emitProgress(mediaInfo, "排队中…", 0)
	select {
	case tr.jobs <- transcribeJob{mediaInfo: mediaInfo, format: format, language: language}:
	default:
		tr.emit(mediaInfo, "转录队列已满，请稍后再试", shared.DownloadStatusError)
	}
}

// runJob 同步执行单个转录任务（由 worker 调用，保证串行）。
func (tr *Transcriber) runJob(mediaInfo shared.MediaInfo, format, language string) {
	filePath := mediaInfo.SavePath
	if _, err := os.Stat(filePath); err != nil {
		tr.emit(mediaInfo, "文件不存在: "+filePath, shared.DownloadStatusError)
		return
	}

	runner, baseArgs, runnerDir, err := tr.resolveRunner()
	if err != nil {
		tr.emit(mediaInfo, err.Error(), shared.DownloadStatusError)
		return
	}

	if format == "" {
		format = globalConfig.SubtitleFormat
	}
	if format == "" {
		format = "srt"
	}

	model := globalConfig.WhisperModel
	if model == "" {
		model = "small"
	}

	// 字幕输出目录：配置了 SubtitleDir 就用它(固定文件夹)，否则放视频同级的 subtitles 子目录
	outDir := globalConfig.SubtitleDir
	if outDir == "" {
		outDir = filepath.Join(filepath.Dir(filePath), "subtitles")
	}
	if err := os.MkdirAll(outDir, 0755); err != nil {
		tr.emit(mediaInfo, "创建字幕目录失败: "+err.Error(), shared.DownloadStatusError)
		return
	}

	args := append([]string{}, baseArgs...) // 回退模式下 baseArgs=[script]，发布模式为空
	args = append(args,
		"-i", filePath,
		"-o", outDir,
		"--model", model,
		"--format", format,
		"--device", "auto",
		"--progress",
	)
	// 模型根目录：配置优先，否则用转录器同级 models/（开发=python/models，发布=transcriber/models）
	modelDir := globalConfig.ModelDir
	if modelDir == "" {
		modelDir = filepath.Join(runnerDir, "models")
	}
	args = append(args, "--model-dir", modelDir)

	lang := language
	if lang == "" {
		lang = globalConfig.SubtitleLanguage
	}
	if lang != "" && lang != "auto" {
		args = append(args, "--language", lang)
	}

	globalLogger.Info().
		Str("runner", runner).
		Str("file", filePath).
		Str("cmd", runner+" "+strings.Join(args, " ")).
		Msg("transcribe start")

	cmd := exec.Command(runner, args...)
	cmd.Dir = runnerDir
	// 确保 Python 输出为 UTF-8，避免 Windows 下 GBK 乱码
	cmd.Env = append(os.Environ(), "PYTHONIOENCODING=utf-8", "PYTHONUTF8=1")
	hideWindow(cmd)

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		tr.emit(mediaInfo, err.Error(), shared.DownloadStatusError)
		return
	}
	cmd.Stderr = cmd.Stdout

	if err := cmd.Start(); err != nil {
		tr.emit(mediaInfo, "启动转录失败: "+err.Error()+" (请确认已安装 Python 和 faster-whisper)", shared.DownloadStatusError)
		return
	}
	tr.tasks.Store(mediaInfo.Id, cmd)
	defer tr.tasks.Delete(mediaInfo.Id)

	tr.emitProgress(mediaInfo, "转录中…", 0)

	var lastLine string
	var subtitlePaths []string
	scanner := bufio.NewScanner(stdout)
	scanner.Buffer(make([]byte, 1024*1024), 1024*1024)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		switch {
		case strings.HasPrefix(line, "__PROGRESS__"):
			if pct, e := strconv.ParseFloat(strings.TrimSpace(strings.TrimPrefix(line, "__PROGRESS__")), 64); e == nil {
				tr.emitProgress(mediaInfo, "转录中…", pct)
			}
		case strings.HasPrefix(line, "__SUBTITLE__"):
			subtitlePaths = append(subtitlePaths, strings.TrimSpace(strings.TrimPrefix(line, "__SUBTITLE__")))
		default:
			lastLine = line
			if strings.Contains(line, "加载模型") {
				tr.emitProgress(mediaInfo, "加载模型…", 0)
			}
		}
	}

	err = cmd.Wait()
	if err != nil {
		msg := "转录失败"
		if lastLine != "" {
			msg = "转录失败: " + lastLine
		}
		tr.emit(mediaInfo, msg, shared.DownloadStatusError)
		return
	}

	// 优先用 python 实际写入并回报的字幕路径(消除路径不一致)
	subPath := ""
	for _, p := range subtitlePaths {
		if strings.HasSuffix(p, ".srt") {
			subPath = p
			break
		}
	}
	if subPath == "" && len(subtitlePaths) > 0 {
		subPath = subtitlePaths[0]
	}
	if subPath == "" {
		// 兜底：按约定推算
		base := strings.TrimSuffix(filepath.Base(filePath), filepath.Ext(filePath))
		ext := ".srt"
		if format == "txt" {
			ext = ".txt"
		}
		subPath = filepath.Join(outDir, base+ext)
	}
	tr.emitDone(mediaInfo, subPath)
}

func (tr *Transcriber) cancel(id string) error {
	if v, ok := tr.tasks.Load(id); ok {
		cmd := v.(*exec.Cmd)
		if cmd.Process != nil {
			_ = cmd.Process.Kill()
		}
		tr.tasks.Delete(id)
		return nil
	}
	return errors.New("task not found")
}

func (tr *Transcriber) emit(mediaInfo shared.MediaInfo, message, status string) {
	if status == shared.DownloadStatusError {
		globalLogger.Error().Str("id", mediaInfo.Id).Str("file", mediaInfo.SavePath).Msg("transcribe error: " + message)
	}
	httpServerOnce.send("transcribeProgress", map[string]interface{}{
		"Id":           mediaInfo.Id,
		"Status":       status,
		"Message":      message,
		"Progress":     0,
		"SubtitlePath": "",
	})
}

func (tr *Transcriber) emitProgress(mediaInfo shared.MediaInfo, message string, pct float64) {
	httpServerOnce.send("transcribeProgress", map[string]interface{}{
		"Id":           mediaInfo.Id,
		"Status":       shared.DownloadStatusRunning,
		"Message":      message,
		"Progress":     pct,
		"SubtitlePath": "",
	})
}

func (tr *Transcriber) emitDone(mediaInfo shared.MediaInfo, subPath string) {
	globalLogger.Info().Str("subtitle", subPath).Msg("transcribe done")
	httpServerOnce.send("transcribeProgress", map[string]interface{}{
		"Id":           mediaInfo.Id,
		"Status":       shared.DownloadStatusDone,
		"Message":      "字幕已生成",
		"Progress":     100,
		"SubtitlePath": subPath,
	})
}
