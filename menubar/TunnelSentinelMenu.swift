import AppKit
import Foundation
import Darwin

private struct Issue {
    let title: String
    let count: Int
}

private struct AISiteCheck {
    let name: String
    let domain: String
    let status: String
    let code: Int
    let ms: Int
    let location: String
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
    var routeManagement = "legacy_external_select"
    var nativeFallbackGroup = ""
    var proxyClient = "shadowrocket"
    var automaticControlEnabled = false
    var tunnelRecoveryEnabled = false
    var deepConnection: [String: Any] = [:]
    var codexStream: [String: Any] = [:]
    var clashMode = ""
    var clashGroup = ""
    var clashGroupType = ""
    var clashParent = ""
    var clashSelectedNode = ""
    var clashActiveConnections = 0
    var clashCandidateCount = 0
    var clashEligibleCount = 0
    var clashDryRunCandidate = ""
    var clashAutoSwitchMode = "simulation_only"
    var clashFailoverState = ""
    var clashFailoverFrom = ""
    var clashFailoverTo = ""
    var clashFailoverActions = 0
    var egressObserved = false
    var egressIP = ""
    var egressColo = ""
    var egressCountry = ""
    var actualBackendName = ""
    var backendVerified = false
    var backendObservedAt = ""
    var backendLastLoggedName = ""
    var backendLastLoggedAt = ""
    var nativeGroupUINode = ""
    var nativeGroupUIObservedAt = 0
    var nativeProxyLogEnabled = false
    var nativeProxyLogRecent = false
    var backendLogHistory: [[String: Any]] = []
    var recoveryState = "monitoring"
    var recoveryReason = ""
    var recoveryRetrySeconds = 0
    var issues: [Issue] = []
    var aiMatrixFresh = false
    var aiMatrixRunning = false
    var aiMatrixCheckedAt = ""
    var aiMatrixSites: [AISiteCheck] = []
    var lastEgressChangeAt = ""
    var lastEgressChangeFrom = ""
    var lastEgressChangeTo = ""
    var lastEgressChangeWithOutage = false
    var endpointMethodResult = ""
    var endpointHeadCode = 0
    var endpointGetCode = 0
    var userLastVerifiedNode = ""
    var userLastVerifiedDate = ""
    var userLastVerifiedGroup = ""
    var screenshotCandidates: [String] = []
    var observedEgressHistory: [[String: Any]] = []
    var lastEdgeOutage: [String: Any] = [:]
}

// NSMenuItem custom views are created before they inherit the menu's effective
// light/dark appearance. Resolve semantic NSColors while drawing, not when
// constructing a CALayer's fixed CGColor; otherwise a dark card can retain
// dark text after attaching to a light system menu (and vice versa).
private final class AppearanceFillView: NSView {
    private let fillColor: NSColor
    private let cornerRadius: CGFloat

    init(frame: NSRect, color: NSColor, cornerRadius: CGFloat = 0) {
        self.fillColor = color
        self.cornerRadius = cornerRadius
        super.init(frame: frame)
    }

    required init?(coder: NSCoder) { nil }

    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)
        fillColor.setFill()
        if cornerRadius > 0 {
            NSBezierPath(roundedRect: bounds, xRadius: cornerRadius, yRadius: cornerRadius).fill()
        } else {
            bounds.fill()
        }
    }
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
        // In-process auto-recovery: no second App, no external AX helper.
        IntegratedRecovery.shared.start()
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
        next.routeManagement = values["route_management"] as? String ?? "legacy_external_select"
        next.nativeFallbackGroup = values["native_fallback_group"] as? String ?? ""
        next.proxyClient = values["proxy_client"] as? String ?? "shadowrocket"
        next.automaticControlEnabled = values["automatic_control_enabled"] as? Bool ?? false
        next.tunnelRecoveryEnabled = values["tunnel_recovery_enabled"] as? Bool ?? false
        next.deepConnection = values["deep_connection_diagnostics"] as? [String:Any] ?? [:]
        next.codexStream = values["codex_stream_diagnostics"] as? [String:Any] ?? [:]
        next.clashAutoSwitchMode = values["clash_auto_switch_mode"] as? String ?? "simulation_only"
        if let failover = values["clash_failover_status"] as? [String:Any] {
            next.clashFailoverState = failover["state"] as? String ?? ""
            next.clashFailoverFrom = failover["from"] as? String ?? ""
            next.clashFailoverTo = failover["to"] as? String ?? ""
            next.clashFailoverActions = failover["actions_today"] as? Int ?? 0
        }
        if let clash = values["clash_observation"] as? [String:Any] {
            next.clashMode = clash["mode"] as? String ?? ""
            next.clashGroup = clash["ai_group"] as? String ?? ""
            next.clashGroupType = clash["ai_group_type"] as? String ?? ""
            next.clashParent = clash["ai_selection"] as? String ?? ""
            next.clashSelectedNode = clash["selected_node"] as? String ?? ""
            next.clashActiveConnections = clash["active_gpt_connections"] as? Int ?? 0
            next.clashCandidateCount = clash["candidate_count"] as? Int ?? 0
            next.clashEligibleCount = clash["eligible_count"] as? Int ?? 0
            next.clashDryRunCandidate = clash["dry_run_candidate"] as? String ?? ""
        }
        // Native AX evidence is read opportunistically by the same approved
        // TunnelSentinel.app; never treat old per-request or screenshot data
        // as the currently selected fallback backend.
        if let reportData = try? Data(contentsOf: base.appendingPathComponent("auto_route_ui_status.json")),
           let report = (try? JSONSerialization.jsonObject(with: reportData)) as? [String: Any],
           report["mode"] as? String == "integrated_app",
           report["enabled"] as? Bool == true,
           let observed = report["checked_at"] as? Int,
           (0...105).contains(Int(Date().timeIntervalSince1970) - observed),
           let node = report["node"] as? String,
           ["JAPAN 04", "JAPAN 14", "SEATTLE 05", "SAN JOSE 07"].contains(node) {
            next.nativeGroupUINode = node
            next.nativeGroupUIObservedAt = observed
        }
        next.egressObserved = values["openai_egress_observed"] as? Bool ?? false
        next.egressIP = values["openai_egress_ip"] as? String ?? ""
        next.egressColo = values["openai_egress_colo"] as? String ?? ""
        next.egressCountry = values["openai_egress_country"] as? String ?? ""
        next.actualBackendName = values["openai_group_backend_name"] as? String ?? ""
        next.backendVerified = values["openai_group_backend_verified"] as? Bool ?? false
        next.backendObservedAt = values["openai_group_backend_observed_at"] as? String ?? ""
        next.nativeProxyLogEnabled = values["native_proxy_log_reader_enabled"] as? Bool ?? false
        next.nativeProxyLogRecent = values["native_proxy_log_recent"] as? Bool ?? false
        if let last = values["native_proxy_last_connection"] as? [String: Any],
           last["source"] as? String == "shadowrocket_native_proxy_log" {
            next.backendLastLoggedName = last["name"] as? String ?? ""
            next.backendLastLoggedAt = last["observed_at"] as? String ?? ""
        }
        next.backendLogHistory = (values["native_proxy_node_history"] as? [[String: Any]] ?? [])
            .filter { $0["source"] as? String == "shadowrocket_native_proxy_log" }
            .suffix(10).map { $0 }
        if let evidence = try? Data(contentsOf: base.appendingPathComponent("group-node-evidence.json")),
           let data = (try? JSONSerialization.jsonObject(with: evidence)) as? [String: Any],
           data["source"] as? String == "human_verified_shadowrocket_ui",
           let name = data["selected_node_at_observation"] as? String,
           let group = data["group"] as? String,
           group == next.nativeFallbackGroup,
           !name.isEmpty {
            next.userLastVerifiedNode = String(name.prefix(90))
            next.userLastVerifiedDate = String((data["observed_date"] as? String ?? "").prefix(24))
            next.userLastVerifiedGroup = group
            next.screenshotCandidates = (data["candidates"] as? [String] ?? []).prefix(16).map { String($0.prefix(90)) }
        }
        next.observedEgressHistory = (values["egress_change_history"] as? [[String: Any]] ?? [])
            .filter { $0["evidence"] as? String == "confirmed_public_edge_egress_change"
                      && $0["native_backend_switch_verified"] as? Bool == false }
            .suffix(6).map { $0 }
        next.lastEdgeOutage = values["last_public_edge_incident"] as? [String: Any] ?? [:]
        next.recoveryState = values["recovery_state"] as? String ?? "monitoring"
        next.recoveryReason = values["recovery_reason"] as? String ?? ""
        next.recoveryRetrySeconds = values["recovery_retry_seconds"] as? Int ?? 0
        if let records = values["business_issues"] as? [[String: Any]] {
            next.issues = records.compactMap {
                guard let title = $0["title"] as? String else { return nil }
                return Issue(title: title, count: $0["count"] as? Int ?? 1)
            }
        }
        next.aiMatrixFresh = values["ai_matrix_fresh"] as? Bool ?? false
        next.aiMatrixRunning = values["ai_matrix_running"] as? Bool ?? false
        next.aiMatrixCheckedAt = values["ai_matrix_checked_at"] as? String ?? ""
        if let audit = values["endpoint_method_audit"] as? [String: Any] {
            next.endpointMethodResult = audit["result"] as? String ?? ""
            next.endpointHeadCode = audit["head_code"] as? Int ?? 0
            next.endpointGetCode = audit["get_code"] as? Int ?? 0
        }
        if let events = values["egress_change_history"] as? [[String: Any]],
           let latest = events.last,
           latest["native_backend_switch_verified"] as? Bool == false,
           latest["evidence"] as? String == "confirmed_public_edge_egress_change" {
            next.lastEgressChangeAt = latest["observed_at"] as? String ?? ""
            next.lastEgressChangeFrom = latest["geo_before"] as? String ?? ""
            next.lastEgressChangeTo = latest["geo_after"] as? String ?? ""
            next.lastEgressChangeWithOutage = latest["preceded_by_recent_public_outage"] as? Bool ?? false
        }
        if let sites = values["ai_matrix_sites"] as? [[String: Any]] {
            next.aiMatrixSites = sites.compactMap { item in
                guard let name = item["name"] as? String,
                      let domain = item["domain"] as? String else { return nil }
                let country = item["egress_country"] as? String ?? ""
                let colo = item["egress_colo"] as? String ?? ""
                return AISiteCheck(
                    name: name, domain: domain,
                    status: item["status"] as? String ?? "unverified",
                    code: item["http_code"] as? Int ?? 0,
                    ms: item["latency_ms"] as? Int ?? 0,
                    location: [country, colo].filter { !$0.isEmpty }.joined(separator: "-"))
            }
        }
        snapshot = next
        guardianPaused = isPaused()
        guardianRunning = isRunning()
        rebuildMenu()
    }

    private func refreshNode() {
        // Native fallback owns OpenAI routing. Guardian already provides the
        // separately labelled *global* selection in status.json. Avoid a
        // redundant cross-App protected-preferences read from this menu app:
        // macOS may show a broad "access data from other apps" TCC prompt.
        if snapshot.routeManagement == "shadowrocket_policy_unverified" || snapshot.routeManagement == "clash_observe_only" { return }
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
        if snapshot.routeManagement == "native_fallback" || snapshot.routeManagement == "clash_observe_only" { return false }
        guard let liveNode, !liveNode.isEmpty else { return false }
        return liveNode != snapshot.checkedNode
    }
    private var nodeUnverified: Bool {
        // Native fallback selects egress independently from the global node.
        // An unreadable global-node preference is not a network fault and
        // should not override a passing OpenAI edge + quiet client diagnostics.
        if snapshot.routeManagement == "native_fallback" || snapshot.routeManagement == "clash_observe_only" { return false }
        return liveNode == nil && !snapshot.nodeVerified
    }

    // This is the *observed proxy egress* from the same live ChatGPT
    // public-edge probe used for health; it is not a Shadowrocket node name.
    private var observedEgress: String {
        guard snapshot.fresh, snapshot.networkHealthy, snapshot.egressObserved,
              !snapshot.egressIP.isEmpty else { return "待确认（尚无有效出口探测）" }
        let place = [snapshot.egressCountry, snapshot.egressColo]
            .filter { !$0.isEmpty }.joined(separator: " · ")
        return place.isEmpty ? snapshot.egressIP : "\(place) · \(snapshot.egressIP)"
    }

    private var shortEgress: String {
        guard snapshot.fresh, snapshot.networkHealthy, snapshot.egressObserved else {
            return "出口待确认"
        }
        let location = [snapshot.egressCountry, snapshot.egressColo]
            .filter { !$0.isEmpty }.joined(separator: "-")
        return location.isEmpty ? "出口已观测" : location
    }

    private var nativeGroupUIRecent: Bool {
        snapshot.fresh && !snapshot.nativeGroupUINode.isEmpty &&
            (0...105).contains(Int(Date().timeIntervalSince1970) - snapshot.nativeGroupUIObservedAt)
    }

    private var backendCompactTitle: String {
        let isRecent = snapshot.fresh && snapshot.backendVerified &&
            !snapshot.actualBackendName.isEmpty
        let historicName = !snapshot.backendLastLoggedName.isEmpty
            ? snapshot.backendLastLoggedName : snapshot.userLastVerifiedNode
        let name = isRecent ? snapshot.actualBackendName : historicName
        guard !name.isEmpty else { return shortEgress }
        let short = String(name
            .replacingOccurrences(of: "🇺🇸 USA ", with: "")
            .replacingOccurrences(of: "🇯🇵 ", with: "")
            .prefix(18))
        return isRecent ? short : "上次 " + short
    }

    private var globalNode: String {
        if let liveNode, !liveNode.isEmpty { return liveNode }
        if snapshot.fresh && !snapshot.checkedNode.isEmpty {
            return snapshot.nodeVerified
                ? snapshot.checkedNode
                : "上次记录 · " + snapshot.checkedNode
        }
        return "未核实"
    }

    private var compactGlobalNode: String {
        let full = globalNode
        if full == "未核实" { return full }
        let isHistory = full.hasPrefix("上次记录 · ")
        let name = isHistory ? String(full.dropFirst("上次记录 · ".count)) : full
        // Name is allowed to be only *last known* when macOS denies current
        // preference access; the prefix preserves the confidence distinction.
        let compact = String(name.replacingOccurrences(of: "🇯🇵 ", with: "")
                                 .replacingOccurrences(of: "🇺🇸 USA ", with: "")
                                 .prefix(14))
        return isHistory ? "上次 " + compact : compact
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
        if guardianPaused { return "监控已暂停 · 当前代理未受影响" }
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
        if snapshot.routeManagement == "clash_observe_only" {
            return "Clash \(snapshot.clashMode.uppercased()) · AI → \(snapshot.clashParent) · 仅监测"
        }
        if snapshot.routeManagement == "shadowrocket_policy_unverified" {
            return "公共入口可达 · Shadowrocket GPT 分组实际命中未核实"
        }
        return "公共入口可达 · 业务错误仅通过客户端日志观察"
    }

    // Single source of truth: the compact status badge and the macOS menu bar
    // must tell users exactly the same state. Keep all state text compact.
    private var statusLabel: String {
        if guardianPaused { return "已暂停" }
        if !guardianRunning { return "离线" }
        if !snapshot.fresh { return "待检测" }
        if nodePending { return "检测中" }
        if !snapshot.networkHealthy && recoveryBlocked { return "需人工处理" }
        if !snapshot.networkHealthy { return "连接异常" }
        if snapshot.business == "attention" { return "需留意" }
        if nodeUnverified { return "节点未核实" }
        return "基础正常"
    }

    private var menuBarStateMarker: String {
        if !snapshot.fresh || guardianPaused || !guardianRunning { return "○" }
        if nodePending { return "◐" }
        if !snapshot.networkHealthy || snapshot.business == "attention" { return "!" }
        if nodeUnverified { return "?" }
        return "●"
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
        // AX-verified NSMenu width is exactly the custom card's 340pt width.
        // Use equal 20pt inset; no speculative additional menu chrome.
        let line = AppearanceFillView(frame: NSRect(x: 20, y: y,
                                                   width: view.bounds.width - 40, height: 1),
                                      color: .separatorColor.withAlphaComponent(0.5))
        view.addSubview(line)
    }

    private func badge(_ text: String, color: NSColor, frame: NSRect) -> NSView {
        let bg = AppearanceFillView(frame: frame,
                                    color: color.withAlphaComponent(0.13), cornerRadius: 9)
        bg.addSubview(label(text, font: .systemFont(ofSize: 11, weight: .semibold),
                            color: color, frame: NSRect(x: 9, y: 1, width: frame.width-18, height: 19),
                            alignment: .center))
        return bg
    }

    private func menuCard() -> NSView {
        let w: CGFloat = 340
        // The native NSMenu owns its vibrancy/material and light/dark appearance.
        // Painting windowBackgroundColor into a fixed-width custom NSMenuItem
        // creates a hard top/bottom color seam and exposes a strip on the right
        // when a localized native menu command widens the menu. Keep the root
        // transparent so the SAME system menu material fills the entire panel.
        let v = NSView(frame: NSRect(x: 0, y: 0, width: w, height: 326))
        v.addSubview(label("T U N N E L   S E N T I N E L",
                           font: .systemFont(ofSize: 10, weight: .bold),
                           color: .tertiaryLabelColor,
                           frame: NSRect(x: 20, y: 290, width: w - 140, height: 19)))
        v.addSubview(badge(statusLabel, color: accent,
                           frame: NSRect(x: w - 98, y: 287, width: 78, height: 22)))
        v.addSubview(label(headline, font: .systemFont(ofSize: 19, weight: .semibold),
                           color: .labelColor, frame: NSRect(x: 20, y: 253, width: w - 40, height: 27)))
        v.addSubview(label(detail, font: .systemFont(ofSize: 11.5),
                           color: .secondaryLabelColor, frame: NSRect(x: 20, y: 230, width: w - 40, height: 19)))

        let nodeBox = AppearanceFillView(frame: NSRect(x: 18, y: 114, width: w - 36, height: 106),
                                         color: .controlBackgroundColor, cornerRadius: 10)
        let clashMode = snapshot.routeManagement == "clash_observe_only"
        let backendSource = clashMode ? "GPT 实际请求节点 · Clash 本地 API" :
            snapshot.fresh && snapshot.networkHealthy && snapshot.egressObserved
            ? "GPT 实测出口 · 周期探测" : "GPT 出口 · 待确认"
        nodeBox.addSubview(label(backendSource,
                                font: .systemFont(ofSize: 10, weight: .medium),
                                color: .secondaryLabelColor,
                                frame: NSRect(x: 12, y: 84, width: nodeBox.bounds.width - 24, height: 15)))
        let egressTitle = clashMode
            ? (snapshot.backendVerified ? snapshot.actualBackendName : "当前没有可确认的 GPT 活跃请求")
            : observedEgress
        nodeBox.addSubview(label(egressTitle,
                                font: .systemFont(ofSize: 13.5, weight: .semibold),
                                color: .labelColor,
                                frame: NSRect(x: 12, y: 57, width: nodeBox.bounds.width - 24, height: 22)))
        nodeBox.addSubview(label(clashMode ? "GPT 公共出口 · 周期探测" :
                                nativeGroupUIRecent ? "GPT 分组节点 · 最近原生界面读取"
                                : "GPT 分组节点 · 暂无近期读取",
                                font: .systemFont(ofSize: 10, weight: .medium),
                                color: .secondaryLabelColor,
                                frame: NSRect(x: 12, y: 35, width: nodeBox.bounds.width - 24, height: 15)))
        nodeBox.addSubview(label(clashMode ? observedEgress :
                                 nativeGroupUIRecent ? snapshot.nativeGroupUINode : "当前节点未核实 · 可查看详细状态",
                                font: .systemFont(ofSize: 13.5, weight: .semibold),
                                color: .labelColor,
                                frame: NSRect(x: 12, y: 9, width: nodeBox.bounds.width - 24, height: 23)))
        v.addSubview(nodeBox)

        divider(105, in: v)
        v.addSubview(label("●", font: .systemFont(ofSize: 13), color: snapshot.networkHealthy ? .systemGreen : .systemRed,
                           frame: NSRect(x: 20, y: 78, width: 16, height: 19)))
        v.addSubview(label("基础链路", font: .systemFont(ofSize: 12, weight: .medium), color: .labelColor,
                           frame: NSRect(x: 40, y: 78, width: 126, height: 19)))
        v.addSubview(label(snapshot.fresh && snapshot.networkHealthy ? "公共入口可达" : "待确认 / 不可达",
                           font: .systemFont(ofSize: 11), color: .secondaryLabelColor,
                           frame: NSRect(x: 164, y: 78, width: w - 184, height: 19), alignment: .right))

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
                           frame: NSRect(x: 139, y: 54, width: w - 159, height: 19), alignment: .right))

        divider(43, in: v)
        let timeText = snapshot.checkedAt.count >= 19
            ? String(snapshot.checkedAt.dropFirst(11).prefix(8)) : "—"
        let recoveryText = recoveryBlocked && snapshot.recoveryRetrySeconds > 0
            ? " · 恢复重试约 \(snapshot.recoveryRetrySeconds / 60) 分钟后"
            : (clashMode ? " · Clash 本地 API" : " · 节点读取受系统权限约束")
        v.addSubview(label("最近检测 \(timeText)\(recoveryText)",
                           font: .systemFont(ofSize: 10), color: .tertiaryLabelColor,
                           frame: NSRect(x: 20, y: 17, width: w - 40, height: 18)))
        return v
    }

    private func menuItem(_ title: String, symbol: String, action: Selector) -> NSMenuItem {
        let item = NSMenuItem(title: title, action: action, keyEquivalent: "")
        item.target = self
        item.image = NSImage(systemSymbolName: symbol, accessibilityDescription: nil)
        return item
    }

    private var aiMatrixSummary: String {
        if !snapshot.aiMatrixFresh {
            return snapshot.aiMatrixRunning ? "AI 分流检测 · 正在检查" : "AI 分流检测 · 待检测"
        }
        let ok = snapshot.aiMatrixSites.filter { $0.status == "reachable" }.count
        return "AI 分流检测 · \(ok)/\(snapshot.aiMatrixSites.count) 可达"
    }

    @objc private func showAIMatrix() {
        let dialog = NSAlert()
        dialog.messageText = "AI 站点分流检测"
        dialog.alertStyle = .informational
        dialog.addButton(withTitle: "关闭")
        if !snapshot.fresh || !snapshot.aiMatrixFresh {
            dialog.informativeText = """
                暂无有效的多站点检测结果。
                后台每约 15 分钟进行一次轻量测试。
                当前基础健康检查与本测试互不影响。
                """
        } else {
            let rows = snapshot.aiMatrixSites.map { site -> String in
                let state = site.status == "reachable" ? "可达" : "未确认"
                let location = site.location.isEmpty ? "—" : site.location
                let timing = site.status == "reachable" ? " · \(site.ms)ms" : ""
                return "\(site.name)  \(state) · \(location)\(timing)"
            }.joined(separator: "\n")
            dialog.informativeText = """
                最近检查：\(snapshot.aiMatrixCheckedAt)

                \(rows)

                仅表示当前代理路径的公共网站可达性及出口地理信息。
                不等于节点支持 ChatGPT 登录、对话或 API。
                其他 AI 网站的失败不会触发 ChatGPT 切换。
                \(methodAuditDescription)
                \(egressHistoryDescription)
                """
        }
        dialog.runModal()
    }

    private var egressHistoryDescription: String {
        guard !snapshot.lastEgressChangeAt.isEmpty else { return "" }
        let former = snapshot.lastEgressChangeFrom.isEmpty ? "地区未确认" : snapshot.lastEgressChangeFrom
        let latest = snapshot.lastEgressChangeTo.isEmpty ? "地区未确认" : snapshot.lastEgressChangeTo
        let nearby = snapshot.lastEgressChangeWithOutage ? "；附近记录有公共入口中断" : ""
        return """

            最近观测到出口变化：\(former) → \(latest)
            时间：\(snapshot.lastEgressChangeAt)\(nearby)
            该变化经两次成功探测确认，但不能证明机场节点已切换。
            """
    }

    private var methodAuditDescription: String {
        guard snapshot.aiMatrixFresh else { return "" }
        switch snapshot.endpointMethodResult {
        case "possible_head_false_negative":
            return """

                当前路径的检测 URL 存在方法差异：
                GET \(snapshot.endpointGetCode) / HEAD \(snapshot.endpointHeadCode)（Cloudflare 验证）
                注意：尚未证明 Shadowrocket 后台采用 HEAD。
                这是待核查风险，不触发节点切换。
                """
        case "no_mismatch_observed":
            return "\n当前路径 HEAD/GET 无已知冲突（不代表全部节点）。"
        case "inconclusive":
            return "\n当前路径 HEAD/GET 检查结果不确定，请勿推断节点失效。"
        default:
            return ""
        }
    }

    private func rebuildMenu() {
        guard let statusItem else { return }
        let fingerprint = [
            headline, detail, liveNode ?? "", snapshot.checkedNode, snapshot.checkedAt,
            snapshot.proxyClient,snapshot.clashMode,snapshot.clashGroup,snapshot.clashParent,
            String(snapshot.automaticControlEnabled),String(snapshot.tunnelRecoveryEnabled),
            String(describing:snapshot.deepConnection),String(describing:snapshot.codexStream),
            snapshot.clashAutoSwitchMode,snapshot.clashFailoverState,
            snapshot.clashFailoverFrom,snapshot.clashFailoverTo,String(snapshot.clashFailoverActions),
            snapshot.clashSelectedNode,String(snapshot.clashActiveConnections),
            String(snapshot.clashCandidateCount),String(snapshot.clashEligibleCount),
            String(snapshot.fresh), String(snapshot.networkHealthy),
            String(guardianRunning), String(guardianPaused), String(nodeUnverified),
            statusLabel, menuBarStateMarker, IntegratedRecovery.shared.summary,
            snapshot.nativeGroupUINode, String(snapshot.nativeGroupUIObservedAt),
            String(snapshot.egressObserved), snapshot.egressIP,
            snapshot.egressCountry, snapshot.egressColo,
            snapshot.actualBackendName, String(snapshot.backendVerified),
            snapshot.backendObservedAt, snapshot.backendLastLoggedName,
            snapshot.backendLastLoggedAt, String(snapshot.nativeProxyLogRecent),
            snapshot.backendLogHistory.map { String(describing: $0) }.joined(separator: "|"),
            snapshot.routeManagement, snapshot.nativeFallbackGroup,
            snapshot.recoveryState, snapshot.recoveryReason,
            String(snapshot.recoveryRetrySeconds),
            snapshot.issues.map { "\($0.title):\($0.count)" }.joined(separator: "|"),
            aiMatrixSummary, snapshot.aiMatrixCheckedAt,
            snapshot.lastEgressChangeAt, snapshot.lastEgressChangeFrom,
            snapshot.lastEgressChangeTo, String(snapshot.lastEgressChangeWithOutage),
            snapshot.userLastVerifiedNode, snapshot.userLastVerifiedDate,
            snapshot.userLastVerifiedGroup, snapshot.screenshotCandidates.joined(separator: "|"),
            snapshot.observedEgressHistory.map { String(describing: $0) }.joined(separator: "|"),
            snapshot.endpointMethodResult, String(snapshot.endpointHeadCode),
            String(snapshot.endpointGetCode),
            snapshot.aiMatrixSites.map { "\($0.domain):\($0.status):\($0.location)" }.joined(separator: "|")
        ].joined(separator: "::")
        guard fingerprint != lastRenderedState else { return }
        lastRenderedState = fingerprint
        // Allow macOS to choose dark/light contrast for both glyph and label.
        // Keep the permanent menu bar compact; never pin a stale provider
        // node or unrelated global Shadowrocket selection next to the clock.
        let compactEdge = snapshot.fresh && snapshot.networkHealthy && snapshot.egressObserved
            && !snapshot.egressCountry.isEmpty ? " · GPT \(shortEgress)" : ""
        statusItem.button?.title = "\(menuBarStateMarker) \(statusLabel)\(compactEdge)"
        statusItem.button?.contentTintColor = nil
        let selectedDescription = snapshot.routeManagement == "clash_observe_only"
            ? "Clash AI→\(snapshot.clashParent)；最近 GPT 请求节点：\(snapshot.backendVerified ? snapshot.actualBackendName : "未核实")；候选：\(snapshot.clashCandidateCount)"
            : nativeGroupUIRecent
            ? "Shadowrocket 分组界面近期选中：\(snapshot.nativeGroupUINode)（仅代表界面读数）"
            : snapshot.fresh && snapshot.backendVerified
            ? "GPT 最近请求实际节点：\(snapshot.actualBackendName)（\(snapshot.backendObservedAt)）"
            : "GPT 当前节点尚未核实；上次请求记录或截图：\(snapshot.backendLastLoggedName.isEmpty ? snapshot.userLastVerifiedNode : snapshot.backendLastLoggedName)（\(snapshot.backendLastLoggedAt.isEmpty ? snapshot.userLastVerifiedDate : snapshot.backendLastLoggedAt)）"
        let routeNodeDescription = snapshot.routeManagement == "clash_observe_only"
            ? "Clash Proxies 当前选中：\(snapshot.clashSelectedNode)"
            : "Shadowrocket 全局节点：\(globalNode)"
        statusItem.button?.toolTip = "TunnelSentinel · \(statusLabel)\n\(headline)\n\(selectedDescription)\nOpenAI 公共出口：\(observedEgress)\n\(routeNodeDescription)\n\(detail)"
        statusItem.button?.setAccessibilityLabel("TunnelSentinel，\(statusLabel)，OpenAI 出口 \(shortEgress)，全局节点 \(globalNode)")
        statusItem.button?.setAccessibilityValue("\(headline)；\(detail)")
        let menu = NSMenu()
        let card = NSMenuItem()
        card.view = menuCard()
        menu.addItem(card)
        menu.addItem(.separator())
        menu.addItem(menuItem("立即检查链路", symbol: "arrow.clockwise", action: #selector(forceProbe)))
        menu.addItem(menuItem(aiMatrixSummary, symbol: "globe.americas",
                              action: #selector(showAIMatrix)))
        menu.addItem(menuItem("查看 GPT 节点状态与事件", symbol: "list.bullet.rectangle", action: #selector(openLog)))
        menu.addItem(menuItem("ChatGPT / Codex 分层诊断", symbol: "stethoscope",
                              action: #selector(showDeepConnection)))
        menu.addItem(menuItem(snapshot.automaticControlEnabled
                              ? "自动节点控制 · 已开启（点击关闭）"
                              : "只读监控 · 自动节点控制已关闭", symbol: "lock.shield",
                              action: #selector(toggleAutomaticControl)))
        menu.addItem(menuItem(snapshot.tunnelRecoveryEnabled
                              ? "隧道掉线重连 · 已开启（点击关闭）"
                              : "隧道掉线重连 · 已关闭（点击开启）", symbol: "arrow.clockwise.circle",
                              action: #selector(toggleTunnelRecovery)))
        let recovery = IntegratedRecovery.shared.summary
        if snapshot.routeManagement == "clash_observe_only" {
            menu.addItem(menuItem(snapshot.clashAutoSwitchMode == "live_guarded"
                                  ? "Clash 自动故障转移 · 已启用"
                                  : "Clash 自动故障转移 · 未启用", symbol: "shield-check",
                                  action: #selector(showClashRecoveryPlan)))
            menu.addItem(menuItem(snapshot.clashAutoSwitchMode == "live_guarded"
                                  ? "关闭 Clash 自动切换"
                                  : "开启 Clash 自动切换", symbol: "arrow.triangle.2.circlepath",
                                  action: #selector(toggleClashRecovery)))
        } else {
            menu.addItem(menuItem(snapshot.routeManagement == "shadowrocket_policy_unverified"
                                  ? "Shadowrocket 节点切换 · 分组未核实（不可用）"
                                  : "节点故障转移 · \(recovery)",
                                  symbol: "lock", action: #selector(showShadowrocketLimits)))
        }
        if (recoveryBlocked || !snapshot.networkHealthy) && snapshot.routeManagement != "clash_observe_only" {
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

    private func nodeEvidenceText() -> String {
        if snapshot.routeManagement == "clash_observe_only" {
            return """
                GPT 节点状态与事件 · Clash Verge
                ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                代理客户端：Clash Verge / Mihomo（\(snapshot.clashMode)）
                GPT 规则分组：\(snapshot.clashGroup) → \(snapshot.clashParent)
                当前组内选中节点：\(snapshot.clashSelectedNode)
                活跃 GPT 请求：\(snapshot.clashActiveConnections)
                本地 API 最近请求节点：\(snapshot.backendVerified ? snapshot.actualBackendName : "无近期证据")
                请求级证据：\(snapshot.backendVerified ? "Mihomo 连接链（非历史出口推测）" : "无当前活跃连接，不能证明此刻实际节点")
                GPT 公共出口：\(observedEgress)

                当前候选：\(snapshot.clashCandidateCount)
                有近期延迟记录：\(snapshot.clashEligibleCount)
                故障切换：\(snapshot.clashAutoSwitchMode == "live_guarded" ? "真实自动切换已启用" : "只读监测")
                最近一次控制器检查：\(snapshot.clashFailoverState.isEmpty ? "暂无记录" : snapshot.clashFailoverState)
                GPT 专用组：TunnelSentinel-OpenAI（不修改共享 AI / Proxies）
                触发：最近210秒内3次 Codex 流错误，最短10分钟冷却，每日最多3次。
                切换后验证节点回读与公共入口；真实 Codex 恢复仍需业务事件验证。
                """
        }
        let group = snapshot.nativeFallbackGroup.isEmpty ? "未配置" : snapshot.nativeFallbackGroup
        let backend: String
        if nativeGroupUIRecent {
            backend = "\(snapshot.nativeGroupUINode)（近45秒内 Shadowrocket 组内界面读数，非请求日志）"
        } else if snapshot.fresh && snapshot.backendVerified && !snapshot.actualBackendName.isEmpty {
            backend = "\(snapshot.actualBackendName)（最近 GPT 请求：\(snapshot.backendObservedAt)，原生记录）"
        } else {
            backend = "当前节点未核实（近期没有新的 GPT 原生代理请求日志）"
        }
        let lastNative = snapshot.backendLastLoggedName.isEmpty
            ? "尚无符合 OpenAI 分组的原生日志"
            : "\(snapshot.backendLastLoggedName)（\(snapshot.backendLastLoggedAt)，上次实际请求）"
        let nativeHistory = snapshot.backendLogHistory.suffix(10).map { item -> String in
            let when = item["observed_at"] as? String ?? "?"
            let from = item["from_node"] as? String ?? "?"
            let to = item["to_node"] as? String ?? "?"
            return "  · \(when)  GPT 请求节点：\(from) → \(to)"
        }.joined(separator: "\n")
        let lastVerified = snapshot.userLastVerifiedNode.isEmpty
            ? "无人工核实记录"
            : "\(snapshot.userLastVerifiedNode)（\(snapshot.userLastVerifiedDate) 界面截图；仅当时选中）"
        let candidates = snapshot.screenshotCandidates.isEmpty
            ? "未获得可靠候选名单"
            : snapshot.screenshotCandidates.joined(separator: "、")
        let edge = snapshot.fresh && snapshot.networkHealthy && snapshot.egressObserved
            ? [snapshot.egressCountry, snapshot.egressColo].filter { !$0.isEmpty }.joined(separator: "-")
            : "待确认"
        let edgeIP = snapshot.fresh && snapshot.networkHealthy && snapshot.egressObserved
            ? snapshot.egressIP : "未观测"
        let health = snapshot.fresh
            ? (snapshot.networkHealthy ? "公共入口可达" : "公共入口异常") : "状态已过期"
        let business = snapshot.business == "attention" ? "有近期业务异常" : "近期未检测到业务异常"
        let lastOutage = snapshot.lastEdgeOutage.isEmpty
            ? "未记录" : "\(snapshot.lastEdgeOutage["observed_at"] as? String ?? "未知时间")；"
                + "采样中断 \(snapshot.lastEdgeOutage["sampled_outage_seconds"] ?? "未知") 秒"
        let changes = snapshot.observedEgressHistory.suffix(6).map { event -> String in
            let moment = event["observed_at"] as? String ?? "时间未确认"
            let former = event["geo_before"] as? String ?? "?"
            let current = event["geo_after"] as? String ?? "?"
            let linked = (event["preceded_by_recent_public_outage"] as? Bool ?? false)
                ? "；附近曾有公共入口中断" : ""
            return "  · \(moment)  出口：\(former) → \(current)\(linked)"
        }.joined(separator: "\n")
        return """
            GPT 节点状态与事件
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            历史配置分组：\(group)（未核实当前 GPT 规则命中）
            自动节点控制：\(snapshot.automaticControlEnabled ? "允许" : "关闭 · 只读")
            隧道自动重连：\(snapshot.tunnelRecoveryEnabled ? "开启" : "关闭")
            最近一次 GPT 请求：\(backend)
            上次原生日志节点：\(lastNative)
            上次人工确认：\(lastVerified)
            上次确认候选：\(candidates)

            当前 GPT 公共入口：\(health)
            客户端业务状态：\(business)
            实际出口地区：\(edge)
            出口 IP（技术参考）：\(edgeIP)
            Shadowrocket 全局节点：\(globalNode)

            GPT 原生节点变更记录
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            \(nativeHistory.isEmpty ? "  尚无不同节点的连续请求证据" : nativeHistory)

            自然故障留证
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            最近公共入口恢复：\(lastOutage)
            最近出口变化：
            \(changes.isEmpty ? "  暂无连续两次确认的出口变化" : changes)

            订阅迁移注意
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            当前 fallback 只绑定指定订阅，不能自动跟随新机场。
            订阅自身更新可刷新候选，但不同机场的节点名可能
            不匹配当前正则筛选条件。换机场后请先检查分组候选数、
            重新指定「服务器节点」及筛选规则，再确认 GPT 规则命中。
            不会自动导入或读取订阅链接、密码等凭据。

            数据可信度说明
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            · 上次人工确认的节点不等于此刻实际使用的节点。
            · IP/地区只证明当前网络出口，不能反推出机场节点名。
            · Shadowrocket 原生代理日志已集成：节点名来自每条 GPT
              请求的命中结果，不等于“持续在线选中”的实时状态。
            · 日志关闭或 10 分钟无新 GPT 连接后不再显示实时节点；
              上次请求保留时间标识，非 GPT 网站活动绝不采集。
            · 这是只读诊断，不会替 Shadowrocket 自动换节点。
            """
    }

    private func refreshLogWindow() {
        let mode = logPicker?.indexOfSelectedItem ?? 0
        let historical = mode == 2
        let rows = mode == 0 ? [] : logLines(historyOnly: historical)
        let pattern = #"(?i)([?&](?:token|key|auth|password|secret)=)[^\s&]+"#
        logTextView?.string = mode == 0
            ? nodeEvidenceText()
            : rows.isEmpty
                ? "暂无相关事件。网络守护仍在运行，最近没有记录到该类型的日志。"
                : rows.map { $0.replacingOccurrences(of: pattern, with: "$1[redacted]",
                                                      options: .regularExpression) }.joined(separator: "\n")
        if mode == 0 {
            logTextView?.scrollToBeginningOfDocument(nil)
        } else {
            logTextView?.scrollToEndOfDocument(nil)
        }
        logSummary?.stringValue = mode == 0
            ? "按节点优先展示 · 来源已标注 · 不读取聊天或订阅凭据"
            : historical
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
        window.title = "TunnelSentinel · GPT 节点与事件"
        window.minSize = NSSize(width: 600, height: 360)
        window.isReleasedWhenClosed = false
        window.center()
        guard let content = window.contentView else { return }
        let background = NSVisualEffectView(frame: content.bounds)
        background.material = .windowBackground
        background.blendingMode = .withinWindow
        background.autoresizingMask = [.width, .height]
        content.addSubview(background)
        let topTitle = label("GPT 节点与事件", font: .systemFont(ofSize: 22, weight: .semibold),
                             color: .labelColor, frame: NSRect(x: 22, y: 508, width: 275, height: 31))
        topTitle.autoresizingMask = [.minYMargin]
        background.addSubview(topTitle)
        let desc = label("节点身份、订阅迁移与恢复证据",
                         font: .systemFont(ofSize: 12), color: .secondaryLabelColor,
                         frame: NSRect(x: 22, y: 486, width: 340, height: 19))
        desc.autoresizingMask = [.minYMargin]
        background.addSubview(desc)
        let picker = NSPopUpButton(frame: NSRect(x: 535, y: 499, width: 195, height: 27))
        picker.addItems(withTitles: ["GPT 节点状态", "最近运行日志", "异常与切换"])
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

    private func recoveryEnabled() -> Bool {
        let path = base.appendingPathComponent("config.json")
        guard let data = try? Data(contentsOf: path),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return false }
        return json["codex_auto_failover_enabled"] as? Bool == true
    }

    private func updateMonitorConfig(_ change: (inout [String:Any]) -> Void) {
        let path = base.appendingPathComponent("config.json")
        guard let source = try? Data(contentsOf:path),
              var settings = (try? JSONSerialization.jsonObject(with:source)) as? [String:Any]
        else { showError("无法读取守护配置"); return }
        change(&settings)
        guard let payload = try? JSONSerialization.data(withJSONObject:settings,
                                                          options:[.prettyPrinted,.sortedKeys])
        else { showError("配置校验失败");return }
        do {
            try payload.write(to:path,options:.atomic)
            let result=runLaunchctl(["kickstart","-k","gui/\(getuid())/\(guardianLabel)"])
            if result.0 != 0 { showError("已写入配置，但 Guardian 重启失败，请检查运行状态") }
            IntegratedRecovery.shared.tick()
            lastRenderedState=""
            refreshStatus()
        } catch { showError("保存监控开关失败") }
    }

    @objc private func toggleAutomaticControl() {
        let enabled = !snapshot.automaticControlEnabled
        if enabled {
            let notice = NSAlert()
            notice.messageText = "开启自动节点控制总开关？"
            notice.informativeText = "目前采用只读监测。此开关仅允许已单独启用且通过验证的后端控制器运行；不会自动更改订阅或打开旧后端开关。"
            notice.addButton(withTitle:"允许")
            notice.addButton(withTitle:"取消")
            guard notice.runModal() == .alertFirstButtonReturn else {return}
        }
        updateMonitorConfig { config in
            config["automatic_control_enabled"]=enabled
            if !enabled {
                config["codex_auto_failover_enabled"]=false
                config["clash_auto_failover_enabled"]=false
                config["codex_auto_preflight_enabled"]=false
            }
        }
    }

    @objc private func toggleTunnelRecovery() {
        let enabled = !snapshot.tunnelRecoveryEnabled
        updateMonitorConfig { settings in settings["tunnel_recovery_enabled"]=enabled }
    }

    @objc private func showDeepConnection() {
        let diag=snapshot.deepConnection
        let state=diag["state"] as? String ?? "pending_or_stale"
        let targets=diag["targets"] as? [[String:Any]] ?? []
        let names=["chatgpt_edge":"ChatGPT 公共入口", "chatgpt_websocket":"ChatGPT WebSocket 传输",
                   "openai_api_tls":"OpenAI API TLS", "openai_auth_tls":"OpenAI 登录 TLS",
                   "chatgpt_desktop_tls":"桌面端关联域名 TLS"]
        let rows=targets.map { item -> String in
            let key=item["name"] as? String ?? "?"
            let code=item["http_code"] as? Int ?? 0
            let state=item["state"] as? String ?? "unverified"
            let ms=item["latency_ms"] as? Int
            return "\(names[key] ?? key)：\(state)，HTTP \(code)\(ms.map { " · \($0)ms" } ?? "")"
        }.joined(separator:"\n")
        let stream=snapshot.codexStream
        let count=stream["recent_counts"] as? [String:Int] ?? [:]
        let failures=["broken_pipe","websocket_handshake","connection_reset"]
            .map { "\($0)=\(count[$0] ?? 0)" }.joined(separator:"，")
        let backend = snapshot.issues.filter { $0.title.contains("浏览器控制") }
            .map { "\($0.count) 条浏览器后端异常" }.joined(separator:"，")
        let dlg=NSAlert()
        dlg.messageText="ChatGPT / Codex 分层诊断（只读）"
        dlg.informativeText="""
            当前代理：\(snapshot.proxyClient)
            自动节点控制：\(snapshot.automaticControlEnabled ? "已开启" : "已关闭")
            深度探测：\(state)

            \(rows.isEmpty ? "无新鲜结果（下一个检测周期自动补齐）" : rows)

            Codex 日志：\(stream["state"] as? String ?? "无记录")
            近 210 秒响应流错误：\(failures)
            浏览器控制后端：\(backend.isEmpty ? "近 3 分钟无已分类报错" : backend)

            HTTP 403/404/421 可能代表鉴权或路径拒绝，TLS 成功不等于登录有效。
            此处不模拟登录、对话、网页点击，也不记录账号数据。
            即使桌面域名 TLS 测试失败，也不能单独判定 Computer Use 故障。
            """
        dlg.addButton(withTitle:"关闭")
        dlg.runModal()
    }

    @objc private func toggleRecovery() {
        let path = base.appendingPathComponent("config.json")
        guard let data = try? Data(contentsOf: path),
              var json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return }
        let newValue = !(json["codex_auto_failover_enabled"] as? Bool == true)
        if newValue && !snapshot.automaticControlEnabled {
            showError("自动控制总开关已关闭。先开启总开关，再选择特定后端；当前保持只读。")
            return
        }
        if newValue && !AXIsProcessTrusted() {
            _ = AXIsProcessTrustedWithOptions(["AXTrustedCheckOptionPrompt":true] as CFDictionary)
            let notice = NSAlert()
            notice.messageText = "请只授权 TunnelSentinel"
            notice.informativeText = "节点切换功能已合并到 TunnelSentinel。请在 macOS「隐私与安全性 → 辅助功能」中允许 TunnelSentinel；无需再授权 Route Controller 或 Python。"
            notice.addButton(withTitle: "打开系统设置")
            notice.addButton(withTitle: "稍后")
            if notice.runModal() == .alertFirstButtonReturn {
                openRecoverySettings()
            }
            return
        }
        json["codex_auto_failover_enabled"] = newValue
        json["codex_auto_preflight_enabled"] = false
        guard let updated = try? JSONSerialization.data(withJSONObject:json,options:[.prettyPrinted,.sortedKeys])
        else { return }
        do {
            try updated.write(to:path,options:.atomic)
            IntegratedRecovery.shared.tick()
            self.lastRenderedState = ""
            self.rebuildMenu()
        } catch { showError("配置保存失败，自动切换状态未改变") }
    }

    @objc private func toggleClashRecovery() {
        let path = base.appendingPathComponent("config.json")
        guard let bytes = try? Data(contentsOf:path),
              var object = (try? JSONSerialization.jsonObject(with:bytes)) as? [String:Any]
        else { showError("无法读取 Guardian 配置");return }
        let newValue = !(object["clash_auto_failover_enabled"] as? Bool == true)
        if newValue && !snapshot.automaticControlEnabled {
            showError("自动控制总开关已关闭。先开启总开关，再选择特定后端。")
            return
        }
        if newValue && (snapshot.clashGroup != "TunnelSentinel-OpenAI"
                         || snapshot.clashGroupType != "Selector") {
            showError("GPT 专用分组未就绪，拒绝启用自动切换")
            return
        }
        object["clash_auto_failover_enabled"] = newValue
        guard let data = try? JSONSerialization.data(withJSONObject:object,
                                                       options:[.prettyPrinted,.sortedKeys])
        else { showError("配置序列化失败");return }
        do {
            try data.write(to:path,options:.atomic)
            let code = runLaunchctl(["kickstart","-k","gui/\(getuid())/\(guardianLabel)"]).0
            if code != 0 { showError("配置已保存，但 Guardian 重启失败；请检查守护进程") }
            lastRenderedState = ""
            refreshStatus()
        } catch { showError("Clash 自动切换设置保存失败") }
    }

    @objc private func showClashRecoveryPlan() {
        let notice=NSAlert()
        notice.messageText="Clash GPT 节点自动恢复"
        notice.informativeText="""
            代理客户端：Clash Verge / Mihomo Unix Socket
            GPT 独立分组：\(snapshot.clashGroup)（\(snapshot.clashGroupType)）
            当前 GPT 选中节点：\(snapshot.clashSelectedNode)
            活跃 GPT 连接：\(snapshot.clashActiveConnections)
            动态候选：\(snapshot.clashCandidateCount) 个
            自动故障转移：\(snapshot.clashAutoSwitchMode == "live_guarded" ? "真实切换已启用" : "未启用")
            最近控制结果：\(snapshot.clashFailoverState.isEmpty ? "暂无记录" : snapshot.clashFailoverState)
            今日自动切换：\(snapshot.clashFailoverActions) 次（上限 3 次）

            Codex 最近210秒≥3次流连接异常时，自动筛选并测试替代节点，
            仅切换 TunnelSentinel-OpenAI 分组；10分钟冷却，失败回滚。
            传输与公共入口验证通过不等于登录后 Codex 流恢复完成。
            """
        notice.addButton(withTitle:"知道了")
        notice.runModal()
    }

    @objc private func showShadowrocketLimits() {
        let dlg=NSAlert()
        dlg.messageText="Shadowrocket 自动节点控制未开放"
        dlg.informativeText="""
            当前只确认系统代理由 Shadowrocket 提供，没有可靠证据证明
            ChatGPT 规则使用历史 OpenAI-Resilience 分组。
            原分组控制依赖固定节点名称和可访问的图形编辑页；
            Mac 锁屏、换机场订阅、分组界面关闭时未通过稳定性验收。

            为避免误修改代理规则，这个版本保持只读，无法从菜单直接启用
            Shadowrocket 分组级自动切换。可继续使用基础健康检测及诊断日志。
            """
        dlg.addButton(withTitle:"知道了")
        dlg.runModal()
    }

    @objc private func openRecoverySettings() {
        let url=URL(string:"x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")!
        NSWorkspace.shared.open(url)
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
