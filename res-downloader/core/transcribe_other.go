//go:build !windows

package core

import "os/exec"

// hideWindow 在非 Windows 平台无需处理。
func hideWindow(cmd *exec.Cmd) {}
