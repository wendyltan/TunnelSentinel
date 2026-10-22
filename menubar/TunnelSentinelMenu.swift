import AppKit
import Foundation
import Darwin

private struct Issue {
    let title: String
    let count: Int
}

private struct Snapshot {
    var fresh = false
    var networkHealthy = false
    var overall = "unknown"
    var business = "no_recent_errors"
    var checkedNode = ""
    var nodeVerified = false
    var checkedAt = ""
    var pid: pid_t = 0
    var tunnelState = "unknown"
    var failures = 0
    var recoveryState = "monitoring"
    var recoveryReason = ""
    var recoveryRetrySeconds = 0
    var issues: [Issue] = []
}

@MainActor
final class TunnelSentinelMenu: NSObject, NSApplicationDelegate {
    private let guardianLabel = "com.wuwendi.openai-link-guardian"
    private let base = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Application Support/OpenAILinkGuardian")
    private let preferencePath = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Group Containers/group.com.liguangming.Shadowrocket/Library/Preferences/group.com.liguangming.Shadowrocket").path
    private let nodePreference = "group.com.liguangming.SelectedServerName"
    private var statusItem: NSStatusItem!
    private var statusTimer: Timer?
    private var nodeTimer: Timer?
    private var nodeLookupBusy = false
    private var lastNodeReadFailedAt: Date?
    private var nodeLookupSuspended = false
    private var liveNode: String?
    private var snapshot = Snapshot()
    private var lastRenderedState = ""
    private var guardianRunning = false
    private var guardianPaused = false
    private var logWindow: NSWindow?
    private var logTextView: NSTextView?
    private var logPicker: NSPopUpButton?
    private var logSummary: NSTextField?

    func applicationDidFinishLaunching(_ notification: Notification) {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        // Template images use the menu bar's native foreground and selection color;
        // never tint status bar text using NSColor, especially in dark appearance.
        if let url = Bundle.main.url(forResource: "MenuBarTemplate", withExtension: "png"),
           let glyph = NSImage(contentsOf: url) {
            glyph.size = NSSize(width: 18, height: 18)
            glyph.isTemplate = true
            statusItem.button?.image = glyph
            statusItem.button?.imagePosition = .imageLeading
        } else {
            let fallback = NSImage(systemSymbolName: "waveform.path", accessibilityDescription: "TunnelSentinel")
            fallback?.isTemplate = true
            statusItem.button?.image = fallback
            statusItem.button?.imagePosition = .imageLeading
        }
        if let url = Bundle.main.url(forResource: "AppIcon", withExtension: "icns"),
           let brandIcon = NSImage(contentsOf: url) {
            NSApp.applicationIconImage = brandIcon
        }
        statusItem.button?.toolTip = "TunnelSentinel · Shadowrocket / ChatGPT"
        refreshStatus()
        refreshNode()
        // Status file is produced on a 30-second cycle; node changes are independent.
        statusTimer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refreshStatus() }
        }
        nodeTimer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refreshNode() }
        }
    }

    private func runLaunchctl(_ arguments: [String]) -> (Int32, String) {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        p.arguments = arguments
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        do {
            try p.run()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            p.waitUntilExit()
            return (p.terminationStatus, String(decoding: data, as: UTF8.self))
        } catch { return (-1, error.localizedDescription) }
    }

    private func isPaused() -> Bool {
        runLaunchctl(["print-disabled", "gui/\(getuid())"]).1
            .contains("\"\(guardianLabel)\" => disabled")
    }

    private func isRunning() -> Bool {
        let r = runLaunchctl(["print", "gui/\(getuid())/\(guardianLabel)"])
        return r.0 == 0 && r.1.contains("state = running")
    }

    private func refreshStatus() {
        let path = base.appendingPathComponent("status.json")
        guard let bytes = try? Data(contentsOf: path),
              let values = (try? JSONSerialization.jsonObject(with: bytes)) as? [String: Any]
        else {
            snapshot = Snapshot()
            guardianPaused = isPaused()
            guardianRunning = isRunning()
            rebuildMenu()
            return
        }
        var next = Snapshot()
        let changed = (try? path.resourceValues(forKeys: [.contentModificationDateKey]))?.contentModificationDate
        next.fresh = changed.map { Date().timeIntervalSince($0) < 120 } ?? false
        next.networkHealthy = values["healthy"] as? Bool ?? false
        next.overall = values["overall_status"] as? String ?? "unknown"
        next.business = values["business_status"] as? String ?? "no_recent_errors"
        next.checkedNode = values["current_node"] as? String ?? ""
        next.nodeVerified = values["current_node_verified"] as? Bool ?? false
        next.checkedAt = values["updated_at"] as? String ?? ""
        next.pid = pid_t(values["pid"] as? Int ?? 0)
        next.tunnelState = values["tunnel_state"] as? String ?? "unknown"
        next.failures = values["recent_failure_score"] as? Int ?? 0
        next.recoveryState = values["recovery_state"] as? String ?? "monitoring"
        next.recoveryReason = values["recovery_reason"] as? String ?? ""
        next.recoveryRetrySeconds = values["recovery_retry_seconds"] as? Int ?? 0
        if let records = values["business_issues"] as? [[String: Any]] {
            next.issues = records.compactMap {
                guard let title = $0["title"] as? String else { return nil }
                return Issue(title: title, count: $0["count"] as? Int ?? 1)
            }
        }
        snapshot = next
        guardianPaused = isPaused()
        guardianRunning = isRunning()
        rebuildMenu()
    }

    private func refreshNode() {
        guard !nodeLookupBusy && !nodeLookupSuspended else { return }
        if let last = lastNodeReadFailedAt, Date().timeIntervalSince(last) < 20 { return }
        nodeLookupBusy = true
        let domain = preferencePath
        let key = nodePreference
        DispatchQueue.global(qos: .utility).async { [weak self] in
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/defaults")
            process.arguments = ["export", domain, "-"]
            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = Pipe()
            var value: String?
            var timedOut = false
            do {
                try process.run()
                // macOS may stall access to Shadowrocket's protected Group Container.
                // Never block the status menu or leave an unbounded waiting read.
                let deadline = Date().addingTimeInterval(1.25)
                while process.isRunning && Date() < deadline {
                    Thread.sleep(forTimeInterval: 0.05)
                }
                if process.isRunning {
                    timedOut = true
                    process.terminate()
                    Thread.sleep(forTimeInterval: 0.1)
                    if process.isRunning { _ = Darwin.kill(process.processIdentifier, SIGKILL) }
                } else {
                    let data = pipe.fileHandleForReading.readDataToEndOfFile()
                    if process.terminationStatus == 0,
                       let dict = try PropertyListSerialization.propertyList(from: data, format: nil)
                            as? [String: Any] {
                        value = dict[key] as? String
                    }
                }
            } catch { }
            Task { @MainActor [weak self] in
                guard let self else { return }
                self.nodeLookupBusy = false
                // A protected-file access can leave a kernel-stalled helper.
                // Disable automatic retries until an explicit manual refresh.
                if timedOut { self.nodeLookupSuspended = true }
                guard let value, !value.isEmpty else {
                    self.lastNodeReadFailedAt = Date()
                    self.rebuildMenu()
                    return
                }
                self.lastNodeReadFailedAt = nil
                if self.liveNode != value {
                    let old = self.liveNode
                    self.liveNode = value
                    self.rebuildMenu()
                    if old != nil && value != self.snapshot.checkedNode {
                        self.requestProbe()
                    }
                }
            }
        }
    }

    private var nodePending: Bool {
        guard let liveNode, !liveNode.isEmpty else { return false }
        return liveNode != snapshot.checkedNode
    }
    private var nodeUnverified: Bool {
        return liveNode == nil && !snapshot.nodeVerified
    }

    private var recoveryBlocked: Bool {
        ["no_candidates", "selector_unavailable", "candidate_unhealthy", "node_unverified"]
            .contains(snapshot.recoveryState)
    }

    private var headline: String {
        if guardianPaused { return "守护已暂停" }
        if !guardianRunning { return "守护服务未运行" }
        if !snapshot.fresh { return "等待最新检测" }
        if nodePending { return "节点已切换，等待检测" }
        if !snapshot.networkHealthy && recoveryBlocked { return "自动恢复受阻 · 需要处理" }
        if !snapshot.networkHealthy { return "代理链路异常" }
        if nodeUnverified { return "基础网络可达 · 节点未核实" }
        if snapshot.business == "attention" { return "发现业务异常" }
        return "网络基础链路正常"
    }

    private var detail: String {
        if guardianPaused { return "手动暂停状态 · Shadowrocket 未受影响" }
        if !guardianRunning { return "后台守护未运行，无法读取实时诊断" }
        if !snapshot.fresh { return "没有足够新的健康检测记录" }
        if nodePending { return "节点名称已同步，新节点的链路健康尚未确认" }
        if !snapshot.networkHealthy && recoveryBlocked {
            return snapshot.recoveryReason.isEmpty ? "节点切换未成功，请核查 Shadowrocket" :
                snapshot.recoveryReason
        }
        if !snapshot.networkHealthy { return "公共入口不可达 · 等待有界恢复检查" }
        if snapshot.business == "attention" { return "代理可达，但客户端近期报告错误" }
        if nodeUnverified { return "Shadowrocket 节点名读取受限；链路仍在独立监测" }
        return "公共入口可达 · 业务错误仅通过客户端日志观察"
    }

    private var accent: NSColor {
        if guardianPaused || !guardianRunning || !snapshot.fresh { return .secondaryLabelColor }
        if nodePending || snapshot.business == "attention" || nodeUnverified { return .systemOrange }
        return snapshot.networkHealthy ? .systemGreen : .systemRed
    }

    private func label(_ text: String, font: NSFont, color: NSColor, frame: NSRect,
                       alignment: NSTextAlignment = .left) -> NSTextField {
        let field = NSTextField(labelWithString: text)
        field.frame = frame
        field.font = font
        field.textColor = color
        field.alignment = alignment
        field.maximumNumberOfLines = 1
        field.lineBreakMode = .byTruncatingTail
        return field
    }

    private func divider(_ y: CGFloat, in view: NSView) {
        let line = NSView(frame: NSRect(x: 20, y: y, width: 336, height: 1))
        line.wantsLayer = true
        line.layer?.backgroundColor = NSColor.separatorColor.withAlphaComponent(0.5).cgColor
        view.addSubview(line)
    }

    private func badge(_ text: String, color: NSColor, frame: NSRect) -> NSView {
        let bg = NSView(frame: frame)
        bg.wantsLayer = true
        bg.layer?.cornerRadius = 9
        bg.layer?.backgroundColor = color.withAlphaComponent(0.13).cgColor
        bg.addSubview(label(text, font: .systemFont(ofSize: 11, weight: .semibold),
                            color: color, frame: NSRect(x: 9, y: 1, width: frame.width-18, height: 19),
                            alignment: .center))
        return bg
    }

    private func menuCard() -> NSView {
        let w: CGFloat = 376
        let v = NSView(frame: NSRect(x: 0, y: 0, width: w, height: 280))
        v.wantsLayer = true
        v.layer?.backgroundColor = NSColor.windowBackgroundColor.cgColor
        v.addSubview(label("T U N N E L   S E N T I N E L",
                           font: .systemFont(ofSize: 10, weight: .bold),
                           color: .tertiaryLabelColor,
                           frame: NSRect(x: 20, y: 244, width: 260, height: 19)))
        let badgeText = guardianPaused ? "已暂停" :
            !guardianRunning ? "离线" :
            nodePending ? "检测中" :
            !snapshot.fresh ? "待检测" :
            nodeUnverified ? "节点未核实" :
            !snapshot.networkHealthy && recoveryBlocked ? "需人工处理" :
            !snapshot.networkHealthy ? "连接异常" :
            snapshot.business == "attention" ? "需留意" : "基础正常"
        v.addSubview(badge(badgeText, color: accent, frame: NSRect(x: 280, y: 241, width: 78, height: 22)))
        v.addSubview(label(headline, font: .systemFont(ofSize: 19, weight: .semibold),
                           color: .labelColor, frame: NSRect(x: 20, y: 207, width: 336, height: 27)))
        v.addSubview(label(detail, font: .systemFont(ofSize: 11.5),
                           color: .secondaryLabelColor, frame: NSRect(x: 20, y: 184, width: 337, height: 19)))

        let nodeBox = NSView(frame: NSRect(x: 18, y: 114, width: 340, height: 60))
        nodeBox.wantsLayer = true
        nodeBox.layer?.cornerRadius = 10
        nodeBox.layer?.backgroundColor = NSColor.controlBackgroundColor.cgColor
        nodeBox.addSubview(label(nodeUnverified ? "SHADOWROCKET · 上次记录" : "SHADOWROCKET · 当前节点",
                                font: .systemFont(ofSize: 10, weight: .medium),
                                color: .secondaryLabelColor,
                                frame: NSRect(x: 12, y: 38, width: 300, height: 16)))
        let nodeName = liveNode ?? (snapshot.nodeVerified
            ? snapshot.checkedNode : snapshot.checkedNode.isEmpty
            ? "节点读取受限" : "未核实 · " + snapshot.checkedNode)
        nodeBox.addSubview(label(nodeName, font: .systemFont(ofSize: 15, weight: .semibold),
                                color: .labelColor, frame: NSRect(x: 12, y: 9, width: 312, height: 25)))
        v.addSubview(nodeBox)

        divider(105, in: v)
        v.addSubview(label("●", font: .systemFont(ofSize: 13), color: snapshot.networkHealthy ? .systemGreen : .systemRed,
                           frame: NSRect(x: 20, y: 78, width: 16, height: 19)))
        v.addSubview(label("基础链路", font: .systemFont(ofSize: 12, weight: .medium), color: .labelColor,
                           frame: NSRect(x: 40, y: 78, width: 126, height: 19)))
        v.addSubview(label(snapshot.fresh && snapshot.networkHealthy ? "公共入口可达" : "待确认 / 不可达",
                           font: .systemFont(ofSize: 11), color: .secondaryLabelColor,
                           frame: NSRect(x: 176, y: 78, width: 180, height: 19), alignment: .right))

        let issueText: String
        if !snapshot.fresh {
            issueText = "无最新日志诊断"
        } else if snapshot.issues.isEmpty {
            issueText = "近 3 分钟未见已识别错误"
        } else {
            issueText = snapshot.issues.prefix(2).map { "\($0.title) ×\($0.count)" }.joined(separator: " · ")
        }
        v.addSubview(label("●", font: .systemFont(ofSize: 13), color: snapshot.issues.isEmpty ? .secondaryLabelColor : .systemOrange,
                           frame: NSRect(x: 20, y: 54, width: 16, height: 19)))
        v.addSubview(label("客户端诊断", font: .systemFont(ofSize: 12, weight: .medium),
                           color: .labelColor, frame: NSRect(x: 40, y: 54, width: 105, height: 19)))
        v.addSubview(label(issueText, font: .systemFont(ofSize: 10.5), color: .secondaryLabelColor,
                           frame: NSRect(x: 139, y: 54, width: 217, height: 19), alignment: .right))

        divider(43, in: v)
        let timeText = snapshot.checkedAt.count >= 19
            ? String(snapshot.checkedAt.dropFirst(11).prefix(8)) : "—"
        let recoveryText = recoveryBlocked && snapshot.recoveryRetrySeconds > 0
            ? " · 恢复重试约 \(snapshot.recoveryRetrySeconds / 60) 分钟后"
            : " · 节点读取受系统权限约束"
        v.addSubview(label("最近检测 \(timeText)\(recoveryText)",
                           font: .systemFont(ofSize: 10), color: .tertiaryLabelColor,
                           frame: NSRect(x: 20, y: 17, width: 334, height: 18)))
        return v
    }

    private func menuItem(_ title: String, symbol: String, action: Selector) -> NSMenuItem {
        let item = NSMenuItem(title: title, action: action, keyEquivalent: "")
        item.target = self
        item.image = NSImage(systemSymbolName: symbol, accessibilityDescription: nil)
        return item
    }

    private func rebuildMenu() {
        guard let statusItem else { return }
        let fingerprint = [
            headline, detail, liveNode ?? "", snapshot.checkedNode, snapshot.checkedAt,
            String(snapshot.fresh), String(snapshot.networkHealthy),
            String(guardianRunning), String(guardianPaused), String(nodeUnverified),
            snapshot.recoveryState, snapshot.recoveryReason,
            String(snapshot.recoveryRetrySeconds),
            snapshot.issues.map { "\($0.title):\($0.count)" }.joined(separator: "|")
        ].joined(separator: "::")
        guard fingerprint != lastRenderedState else { return }
        lastRenderedState = fingerprint
        // Allow macOS to choose dark/light contrast for both glyph and label.
        statusItem.button?.title = (recoveryBlocked && !snapshot.networkHealthy) ? "AI !" : "AI"
        statusItem.button?.contentTintColor = nil
        statusItem.button?.toolTip = "\(headline) · \(liveNode ?? snapshot.checkedNode)"
        let menu = NSMenu()
        let card = NSMenuItem()
        card.view = menuCard()
        menu.addItem(card)
        menu.addItem(.separator())
        menu.addItem(menuItem("立即检查链路", symbol: "arrow.clockwise", action: #selector(forceProbe)))
        menu.addItem(menuItem("查看事件日志", symbol: "list.bullet.rectangle", action: #selector(openLog)))
        if recoveryBlocked || !snapshot.networkHealthy {
            menu.addItem(menuItem("打开 Shadowrocket 手动处理", symbol: "network",
                                  action: #selector(openShadowrocket)))
        }
        menu.addItem(.separator())
        menu.addItem(menuItem(guardianPaused ? "开启自动守护" : "暂停自动守护",
                              symbol: guardianPaused ? "play.circle" : "pause.circle",
                              action: #selector(toggleGuardian)))
        menu.addItem(menuItem("退出菜单栏（守护继续运行）",
                              symbol: "xmark.circle", action: #selector(quitMenu)))
        statusItem.menu = menu
    }

    private func requestProbe() {
        guard guardianRunning, snapshot.fresh, snapshot.pid > 1 else { return }
        // Only signals a verified live guardian PID from the fresh status file.
        if kill(snapshot.pid, 0) == 0 {
            _ = kill(snapshot.pid, SIGUSR1)
        }
    }

    @objc private func openShadowrocket() {
        guard let url = NSWorkspace.shared.urlForApplication(
            withBundleIdentifier: "com.liguangming.Shadowrocket") else {
            showError("未找到 Shadowrocket 应用程序")
            return
        }
        NSWorkspace.shared.openApplication(
            at: url, configuration: NSWorkspace.OpenConfiguration(),
            completionHandler: nil)
    }

    @objc private func forceProbe() {
        nodeLookupSuspended = false
        lastNodeReadFailedAt = nil
        requestProbe()
        refreshStatus()
        refreshNode()
    }

    private func showError(_ text: String) {
        let alert = NSAlert()
        alert.messageText = "TunnelSentinel 无法完成操作"
        alert.informativeText = text
        alert.alertStyle = .warning
        alert.runModal()
    }

    @objc private func toggleGuardian() {
        let name = "gui/\(getuid())/\(guardianLabel)"
        let plist = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/LaunchAgents/\(guardianLabel).plist").path
        if guardianPaused {
            let enabled = runLaunchctl(["enable", name])
            if enabled.0 != 0 { showError(enabled.1); refreshStatus(); return }
            if !isRunning() {
                let start = runLaunchctl(["bootstrap", "gui/\(getuid())", plist])
                if start.0 != 0 { showError(start.1) }
            }
        } else {
            let disabled = runLaunchctl(["disable", name])
            if disabled.0 != 0 { showError(disabled.1); refreshStatus(); return }
            if isRunning() {
                let stopped = runLaunchctl(["bootout", name])
                if stopped.0 != 0 { showError(stopped.1) }
            }
        }
        refreshStatus()
    }

    private func logLines(historyOnly: Bool) -> [String] {
        let folder = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Logs/OpenAILinkGuardian")
        let names = historyOnly ? ["guardian.log.2", "guardian.log.1", "guardian.log"] : ["guardian.log"]
        let markers = [
            "failover triggered", "trying node=", "failover succeeded", "node verification failed",
            "all candidates failed", "Shadowrocket tunnel is down", "requesting reconnect",
            "tunnel=down", "guardian cycle failed", "new ChatGPT network log failures="
        ]
        var lines: [String] = []
        for name in names {
            let url = folder.appendingPathComponent(name)
            guard let data = try? Data(contentsOf: url),
                  let content = String(data: data, encoding: .utf8) else { continue }
            let raw = content.components(separatedBy: .newlines)
            lines += historyOnly ? raw.filter { row in markers.contains { row.contains($0) } } : Array(raw.suffix(220))
        }
        return Array(lines.filter { !$0.isEmpty }.suffix(220))
    }

    private func refreshLogWindow() {
        let historical = logPicker?.indexOfSelectedItem == 1
        let rows = logLines(historyOnly: historical)
        let pattern = #"(?i)([?&](?:token|key|auth|password|secret)=)[^\s&]+"#
        logTextView?.string = rows.isEmpty
            ? "暂无相关事件。网络守护仍在运行，最近没有记录到该类型的日志。"
            : rows.map { $0.replacingOccurrences(of: pattern, with: "$1[redacted]",
                                                  options: .regularExpression) }.joined(separator: "\n")
        logTextView?.scrollToEndOfDocument(nil)
        logSummary?.stringValue = historical
            ? "仅列出切换、连接失败及恢复事件 · 最近 220 条"
            : "守护进程运行记录 · 最近 220 条 · 不包含聊天内容"
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
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 860, height: 565),
                              styleMask: [.titled, .closable, .miniaturizable, .resizable],
                              backing: .buffered, defer: false)
        window.title = "TunnelSentinel · 事件记录"
        window.minSize = NSSize(width: 600, height: 360)
        window.isReleasedWhenClosed = false
        window.center()
        guard let content = window.contentView else { return }
        let background = NSVisualEffectView(frame: content.bounds)
        background.material = .windowBackground
        background.blendingMode = .withinWindow
        background.autoresizingMask = [.width, .height]
        content.addSubview(background)
        let topTitle = label("网络事件", font: .systemFont(ofSize: 22, weight: .semibold),
                             color: .labelColor, frame: NSRect(x: 22, y: 508, width: 275, height: 31))
        topTitle.autoresizingMask = [.minYMargin]
        background.addSubview(topTitle)
        let desc = label("连接状态、自动恢复与诊断记录",
                         font: .systemFont(ofSize: 12), color: .secondaryLabelColor,
                         frame: NSRect(x: 22, y: 486, width: 340, height: 19))
        desc.autoresizingMask = [.minYMargin]
        background.addSubview(desc)
        let picker = NSPopUpButton(frame: NSRect(x: 535, y: 499, width: 195, height: 27))
        picker.addItems(withTitles: ["最近运行日志", "异常与切换"])
        picker.target = self
        picker.action = #selector(changeLogMode(_:))
        picker.autoresizingMask = [.minXMargin, .minYMargin]
        background.addSubview(picker)
        logPicker = picker
        let refresh = NSButton(frame: NSRect(x: 734, y: 499, width: 105, height: 28))
        refresh.title = "刷新"
        refresh.bezelStyle = .rounded
        refresh.target = self
        refresh.action = #selector(refreshLog(_:))
        refresh.autoresizingMask = [.minXMargin, .minYMargin]
        background.addSubview(refresh)

        let scroll = NSScrollView(frame: NSRect(x: 22, y: 52, width: 816, height: 418))
        scroll.hasVerticalScroller = true
        scroll.autohidesScrollers = true
        scroll.borderType = .noBorder
        scroll.wantsLayer = true
        scroll.layer?.cornerRadius = 10
        scroll.layer?.backgroundColor = NSColor.textBackgroundColor.cgColor
        scroll.autoresizingMask = [.width, .height]
        let textView = NSTextView(frame: scroll.bounds)
        textView.isEditable = false
        textView.isSelectable = true
        textView.isRichText = false
        textView.font = NSFont.monospacedSystemFont(ofSize: 11, weight: .regular)
        textView.textColor = .labelColor
        textView.textContainerInset = NSSize(width: 14, height: 12)
        scroll.documentView = textView
        background.addSubview(scroll)
        logTextView = textView
        let footer = label("", font: .systemFont(ofSize: 11), color: .secondaryLabelColor,
                           frame: NSRect(x: 22, y: 21, width: 810, height: 18))
        footer.autoresizingMask = [.width]
        background.addSubview(footer)
        logSummary = footer
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
