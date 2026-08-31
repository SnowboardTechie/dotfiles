import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

QtObject {
  id: root

  // Injected by omarchy-shell after the service is created.
  property var shell: null

  readonly property string home: Quickshell.env("HOME")
  readonly property string stayAwakeDir: home + "/.local/state/omarchy/indicators"
  readonly property string stayAwakePath: stayAwakeDir + "/stay-awake"
  readonly property int suspendTimeoutSeconds: 45 * 60
  readonly property bool idleAllowed: stayAwakeStateLoaded && !stayAwake
  readonly property bool suspendEnabled: idleAllowed && suspendTimeoutSeconds > 0

  property bool stayAwake: false
  property bool stayAwakeStateLoaded: false
  property bool stayAwakeRefreshPending: false

  function refreshStayAwake() {
    if (stayAwakeProbe.running) {
      stayAwakeRefreshPending = true
      return
    }
    stayAwakeProbe.running = true
  }

  function suspendIfStillIdle() {
    if (!suspendEnabled || !suspendMonitor.isIdle || suspendProcess.running) return
    console.log("snowboardtechie.auto-suspend: suspending after " + suspendTimeoutSeconds + " seconds idle")
    suspendProcess.running = true
  }

  // A separate monitor leaves Omarchy's screensaver and lock timers untouched.
  // Omarchy's Stay Awake state gates this monitor, while the compositor gates
  // it for application/window idle inhibitors.
  property IdleMonitor suspendMonitor: IdleMonitor {
    enabled: root.suspendEnabled
    timeout: root.suspendTimeoutSeconds
    respectInhibitors: true
    onIsIdleChanged: if (isIdle) root.suspendIfStillIdle()
  }

  // Omarchy's omarchy-sleep-lock.service handles locking before system sleep.
  property Process suspendProcess: Process {
    command: ["systemctl", "suspend"]
    onExited: function(exitCode, exitStatus) {
      if (exitCode !== 0)
        console.warn("snowboardtechie.auto-suspend: systemctl suspend failed with exit code " + exitCode)
    }
  }

  // This is the same state file managed by Omarchy's Stay Awake indicator and
  // `omarchy toggle idle`. A direct `test` avoids introducing a shell command.
  property Process stayAwakeProbe: Process {
    command: ["test", "!", "-f", root.stayAwakePath]
    onExited: function(exitCode, exitStatus) {
      if (exitCode > 1)
        console.warn("snowboardtechie.auto-suspend: failed to read Stay Awake state")
      root.stayAwake = exitCode !== 0
      root.stayAwakeStateLoaded = true
      if (root.stayAwakeRefreshPending) {
        root.stayAwakeRefreshPending = false
        root.refreshStayAwake()
      }
    }
  }

  property FileView stayAwakeWatcher: FileView {
    path: root.stayAwakeDir
    watchChanges: true
    printErrors: false
    onFileChanged: root.refreshStayAwake()
  }

  // Read-only diagnostics: omarchy-shell autoSuspend status
  property IpcHandler ipc: IpcHandler {
    target: "autoSuspend"

    function status(): string {
      return JSON.stringify({
        enabled: root.suspendEnabled,
        idleAllowed: root.idleAllowed,
        stayAwake: root.stayAwake,
        stayAwakeStateLoaded: root.stayAwakeStateLoaded,
        idle: root.suspendMonitor.isIdle,
        timeout: root.suspendTimeoutSeconds,
        suspendProcessRunning: root.suspendProcess.running
      })
    }
  }

  Component.onCompleted: refreshStayAwake()
}
