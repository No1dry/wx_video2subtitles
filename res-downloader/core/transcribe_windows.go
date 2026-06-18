//go:build windows

package core

import (
	"os/exec"
	"syscall"
)

// hideWindow 阻止 Windows 下弹出黑色控制台窗口。
func hideWindow(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
}
