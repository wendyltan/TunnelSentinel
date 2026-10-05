import AppKit
import Foundation

@MainActor
final class TunnelSentinelMenu: NSObject, NSApplicationDelegate {
    private let label = "com.wuwendi.openai-link-guardian"
    private let base = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Application Support/OpenAILinkGuardian")
    private var statusItem: NSStatusItem!
    private var timer: Timer?
    private var logWindow: NSWindow?
    private var logTextView: NSTextView?
    private var logModePicker: NSPopUpButton?
    private var logSummary: NSTextField?

    private var servicePath: String { "gui/\(getuid())/\(label)" }
    private var launchPlist: String {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/LaunchAgents/\(label).plist").path
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.toolTip = "TunnelSentinel · ChatGPT / Shadowrocket 网络守护"
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 12, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refresh() }
        }
    }

    private func run(_ arguments: [String]) -> (Int32, String) {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        process.arguments = arguments
        let out = Pipe()
        process.standardOutput = out
        process.standardError = out
        do {
            try process.run()
            let data = out.fileHandleForReading.readDataToEndOfFile()
            process.waitUntilExit()
            return (process.terminationStatus, String(decoding: data, as: UTF8.self))
        } catch {
            return (-1, error.localizedDescription)
        }
    }

    private func isPaused() -> Bool {
        let result = run(["print-disabled", "gui/\(getuid())"])
        return result.1.contains("\"\(label)\" => disabled")
    }

    private func isRunning() -> Bool {
        let result = run(["print", servicePath])
        return result.0 == 0 && result.1.contains("state = running")
    }

    private func readStatus() -> (healthy: Bool, fresh: Bool, node: String, nodeVerified: Bool) {
        let path = base.appendingPathComponent("status.json").path
        guard let data = FileManager.default.contents(atPath: path),
              let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
        else { return (false, false, "", false) }
        let stamp = (try? FileManager.default.attributesOfItem(atPath: path)[.modificationDate]) as? Date
        let fresh = stamp.map { abs($0.timeIntervalSinceNow) < 120 } ?? false
        return (
            json["healthy"] as? Bool ?? false,
            fresh,
            json["current_node"] as? String ?? "",
            json["current_node_verified"] as? Bool ?? false
        )
    }

    private func item(_ title: String, _ selector: Selector? = nil) -> NSMenuItem {
        let result = NSMenuItem(title: title, action: selector, keyEquivalent: "")
        if selector != nil { result.target = self }
        else { result.isEnabled = false }
        return result
    }

    private func refresh() {
        let paused = isPaused()
        let running = isRunning()
        let status = readStatus()
        let headline: String
        if paused { headline = "AI 暂停" }
        else if !running { headline = "AI 离线" }
        else if !status.fresh { headline = "AI 待检" }
        else if status.healthy { headline = "AI ✓" }
        else { headline = "AI !" }
        statusItem.button?.title = headline
        let menu = NSMenu()
        menu.addItem(item("TunnelSentinel · 网络守护"))
        menu.addItem(.separator())
        let detail = paused ? "已手动暂停守护" :
            !running ? "守护进程未运行" :
            !status.fresh ? "状态信息过期 / 等待检测" :
            status.healthy ? "代理链路检测正常" : "代理链路检测异常"
        menu.addItem(item("状态：\(detail)"))
        if !paused {
            let node = running && status.fresh && status.nodeVerified && !status.node.isEmpty
                ? "Shadowrocket 当前节点：\(status.node)"
                : "Shadowrocket 当前节点：未知"
            menu.addItem(item(node))
        }
        menu.addItem(.separator())
        if paused {
            menu.addItem(item("开启自动守护", #selector(toggleGuardian)))
        } else {
            menu.addItem(item("暂停自动守护（不关闭 Shadowrocket）", #selector(toggleGuardian)))
        }
        menu.addItem(item("立即刷新状态", #selector(forceRefresh)))
        menu.addItem(item("查看守护日志", #selector(openLog)))
        menu.addItem(.separator())
        menu.addItem(item("退出状态栏图标（守护继续运行）", #selector(quitMenu)))
        statusItem.menu = menu
    }

    private func showError(_ message: String) {
        let alert = NSAlert()
        alert.messageText = "TunnelSentinel 操作未完成"
        alert.informativeText = message
        alert.alertStyle = .warning
        alert.runModal()
    }

    @objc private func toggleGuardian() {
        if isPaused() {
            let enable = run(["enable", servicePath])
            if enable.0 != 0 { showError(enable.1); refresh(); return }
            if !isRunning() {
                let boot = run(["bootstrap", "gui/\(getuid())", launchPlist])
                if boot.0 != 0 { showError(boot.1); refresh(); return }
            }
        } else {
            let disable = run(["disable", servicePath])
            if disable.0 != 0 { showError(disable.1); refresh(); return }
            if isRunning() {
                let bootout = run(["bootout", servicePath])
                if bootout.0 != 0 { showError(bootout.1); refresh(); return }
            }
        }
        refresh()
    }

    @objc private func forceRefresh() { refresh() }

    // Open logs inside this app; do not expose credentials or open Finder.
    private func logLines(historyOnly: Bool) -> [String] {
        let folder = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Logs/OpenAILinkGuardian")
        let filenames = historyOnly
            ? ["guardian.log.2", "guardian.log.1", "guardian.log"]
            : ["guardian.log"]
        let markers = [
            "failover triggered", "trying node=", "failover succeeded",
            "node verification failed", "all candidates failed",
            "Shadowrocket tunnel is down", "requesting reconnect",
            "tunnel=down", "guardian cycle failed"
        ]
        var lines: [String] = []
        for filename in filenames {
            let url = folder.appendingPathComponent(filename)
            guard let data = try? Data(contentsOf: url),
                  let content = String(data: data, encoding: .utf8) else { continue }
            let raw = content.components(separatedBy: .newlines)
            if historyOnly {
                lines += raw.filter { line in markers.contains { line.contains($0) } }
            } else {
                lines += Array(raw.suffix(220))
            }
        }
        return Array(lines.filter { !$0.isEmpty }.suffix(220))
    }

    private func safeLogLine(_ line: String) -> String {
        let pattern = #"(?i)([?&](?:token|key|auth|password|secret)=)[^\s&]+"#
        return line.replacingOccurrences(
            of: pattern, with: "$1[redacted]", options: .regularExpression
        )
    }

    private func refreshLogWindow() {
        let historical = logModePicker?.indexOfSelectedItem == 1
        let lines = logLines(historyOnly: historical)
        logTextView?.string = lines.isEmpty
            ? "暂无对应日志；可能尚未发生过切换，或日志文件不存在。"
            : lines.map(safeLogLine).joined(separator: "\n")
        logTextView?.scrollToEndOfDocument(nil)
        logSummary?.stringValue = historical
            ? "从当前日志及两份轮转日志中筛选最多 220 条切换/异常记录。"
            : "显示最近最多 220 条日志；每次点击“刷新”重新读取。"
    }

    @objc private func changeLogMode(_ sender: NSPopUpButton) { refreshLogWindow() }
    @objc private func refreshLog(_ sender: NSButton) { refreshLogWindow() }

    @objc private func openLog() {
        if let window = logWindow {
            refreshLogWindow()
            window.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
            return
        }
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 900, height: 590),
            styleMask: [.titled, .closable, .resizable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        window.title = "TunnelSentinel · 守护日志"
        window.minSize = NSSize(width: 640, height: 360)
        window.isReleasedWhenClosed = false
        window.center()

        guard let content = window.contentView else { return }
        let picker = NSPopUpButton(frame: NSRect(x: 16, y: 543, width: 260, height: 28))
        picker.addItems(withTitles: ["最近日志", "切换与异常历史"])
        picker.target = self
        picker.action = #selector(changeLogMode(_:))
        picker.autoresizingMask = [.minYMargin]
        content.addSubview(picker)
        logModePicker = picker

        let refresh = NSButton(frame: NSRect(x: 780, y: 543, width: 102, height: 28))
        refresh.title = "刷新日志"
        refresh.bezelStyle = .rounded
        refresh.target = self
        refresh.action = #selector(refreshLog(_:))
        refresh.autoresizingMask = [.minXMargin, .minYMargin]
        content.addSubview(refresh)

        let scroll = NSScrollView(frame: NSRect(x: 16, y: 48, width: 868, height: 482))
        scroll.hasVerticalScroller = true
        scroll.hasHorizontalScroller = true
        scroll.autohidesScrollers = true
        scroll.borderType = .bezelBorder
        scroll.autoresizingMask = [.width, .height]
        let textView = NSTextView(frame: scroll.bounds)
        textView.isEditable = false
        textView.isSelectable = true
        textView.isRichText = false
        textView.font = NSFont.monospacedSystemFont(ofSize: 11, weight: .regular)
        textView.textContainerInset = NSSize(width: 8, height: 8)
        textView.isHorizontallyResizable = true
        textView.textContainer?.widthTracksTextView = false
        textView.textContainer?.containerSize = NSSize(width: 2500, height: CGFloat.greatestFiniteMagnitude)
        scroll.documentView = textView
        content.addSubview(scroll)
        logTextView = textView

        let summary = NSTextField(labelWithString: "")
        summary.frame = NSRect(x: 16, y: 14, width: 868, height: 22)
        summary.autoresizingMask = [.width]
        content.addSubview(summary)
        logSummary = summary
        logWindow = window
        refreshLogWindow()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc private func quitMenu() { NSApplication.shared.terminate(nil) }
}

@main
struct TunnelSentinelMenuMain {
    static func main() {
        let app = NSApplication.shared
        app.setActivationPolicy(.accessory)
        let delegate = TunnelSentinelMenu()
        app.delegate = delegate
        app.run()
    }
}
