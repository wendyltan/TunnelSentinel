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
    var proxyClient = "unknown"
    var systemProxyState = ""
    var systemProxyEndpoint = ""
    var systemProxyType = ""
    var automaticControlEnabled = false
    var tunnelRecoveryEnabled = false
    var deepConnection: [String: Any] = [:]
    var codexStream: [String: Any] = [:]
    var uploadProbe: [String: Any] = [:]
    var uploadNodeHistory: [[String: Any]] = []
    var uploadAdvice: [String: Any] = [:]
    var shadowrocketNode: [String: Any] = [:]
    var workflowHealth: [String: Any] = [:]
    var computerUseObservation: [String: Any] = [:]
    var clientEventCorrelation: [String: Any] = [:]
    var workflowTimeline: [String: Any] = [:]
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
    var backendEvidenceSource = ""
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

private final class DashboardFlippedView: NSView {
    override var isFlipped: Bool { true }
}

// NSMenuItem custom views are created before they inherit the menu's effective
// light/dark appearance. Resolve semantic NSColors while drawing, not when
// constructing a CALayer's fixed CGColor; otherwise a dark card can retain
// dark text after attaching to a light system menu (and vice versa).
// Role-based, appearance-aware surfaces. "controlColor" intentionally is NOT a
// dark-theme card color: on macOS Dark Aqua it can resolve to light grey.
private enum SentinelSurface {
    case hero, tile, event, row, menu

    func fill(isDark: Bool) -> NSColor {
        func rgb(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat) -> NSColor {
            NSColor(srgbRed: r/255, green: g/255, blue: b/255, alpha: 1)
        }
        if isDark {
            switch self {
            case .hero: return rgb(33, 43, 55)  // restrained blue-black summary
            case .tile: return rgb(35, 39, 45)  // nearly background, never bright grey
            case .event: return rgb(36, 40, 47)
            case .row: return rgb(30, 33, 38)   // dense diagnostic list
            case .menu: return rgb(32, 37, 43)
            }
        }
        switch self {
        case .hero: return rgb(243, 248, 253)
        case .tile: return rgb(250, 251, 253)
        case .event: return rgb(249, 250, 252)
        case .row: return rgb(253, 253, 254)
        case .menu: return rgb(247, 248, 250)
        }
    }
}

private final class AppearanceFillView: NSView {
    private let fillColor: NSColor
    private let cornerRadius: CGFloat
    private let surface: SentinelSurface?

    init(frame: NSRect, color: NSColor, cornerRadius: CGFloat = 0,
         surface: SentinelSurface? = nil) {
        self.fillColor = color
        self.cornerRadius = cornerRadius
        self.surface = surface
        super.init(frame: frame)
    }

    required init?(coder: NSCoder) { nil }

    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)
        let dark = effectiveAppearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
        let resolved = surface?.fill(isDark: dark) ?? fillColor
        resolved.setFill()
        if cornerRadius > 0 {
            let path = NSBezierPath(roundedRect: bounds, xRadius: cornerRadius,
                                    yRadius: cornerRadius)
            path.fill()
            if surface != nil || cornerRadius >= 12 {
                // Thin hierarchy only. Big opaque grey slabs destroy dark contrast.
                let stroke: NSColor = dark
                    ? NSColor.white.withAlphaComponent(0.10)
                    : NSColor.black.withAlphaComponent(0.075)
                stroke.setStroke()
                let outline = NSBezierPath(roundedRect: bounds.insetBy(dx: 0.5, dy: 0.5),
                                           xRadius: cornerRadius, yRadius: cornerRadius)
                outline.lineWidth = 0.7
                outline.stroke()
            }
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
    private var statusItem: NSStatusItem!
    private var statusTimer: Timer?
    private var liveNode: String?
    private var snapshot = Snapshot()
    private var lastRenderedState = ""
    private var guardianRunning = false
    private var guardianPaused = false
    private var servicePollRunning = false
    private var serviceLastPollAt = Date.distantPast
    private var logWindow: NSWindow?
    private var logTextView: NSTextView?
    private var logPicker: NSPopUpButton?
    private var logSummary: NSTextField?
    private var dashboardWindow: NSWindow?
    private var dashboardTabs: NSSegmentedControl?
    private var dashboardScroll: NSScrollView?
    private var dashboardSelection = 0
    private var expandedTimelineEvents = Set<String>()
    private var timelineVisibleIDs: [String] = []
    private var configUpdateBusy = false
    private var codexProxyEnvBusy = false

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
        statusItem.button?.toolTip = "TunnelSentinel · ChatGPT / Codex 网络监控"
        refreshStatus()
        refreshNode()
        // In-process auto-recovery: no second App, no external AX helper.
        // Status file is produced on a 30-second cycle; node changes are independent.
        statusTimer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refreshStatus() }
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

    // launchctl is a process call and may stall. Check it off the main
    // thread, at most once per 15 seconds; draw the UI from cached values.
    private func pollGuardianServiceIfNeeded() {
        guard !servicePollRunning, Date().timeIntervalSince(serviceLastPollAt) >= 15 else { return }
        servicePollRunning = true
        serviceLastPollAt = Date()
        let label = guardianLabel
        let uid = getuid()
        DispatchQueue.global(qos: .utility).async { [weak self] in
            func query(_ args: [String]) -> (Int32, String) {
                let process = Process()
                process.executableURL = URL(fileURLWithPath: "/bin/launchctl")
                process.arguments = args
                let pipe = Pipe()
                process.standardOutput = pipe
                process.standardError = pipe
                do {
                    try process.run()
                    let data = pipe.fileHandleForReading.readDataToEndOfFile()
                    process.waitUntilExit()
                    return (process.terminationStatus, String(decoding: data, as: UTF8.self))
                } catch { return (-1, "") }
            }
            let paused = query(["print-disabled", "gui/\(uid)"]).1
                .contains("\"\(label)\" => disabled")
            let result = query(["print", "gui/\(uid)/\(label)"])
            let running = result.0 == 0 && result.1.contains("state = running")
            DispatchQueue.main.async { [weak self] in
                guard let self else { return }
                self.guardianPaused = paused
                self.guardianRunning = running
                self.servicePollRunning = false
                self.rebuildMenu()
            }
        }
    }

    private func refreshStatus() {
        pollGuardianServiceIfNeeded()
        let path = base.appendingPathComponent("status.json")
        guard let bytes = try? Data(contentsOf: path),
              let values = (try? JSONSerialization.jsonObject(with: bytes)) as? [String: Any]
        else {
            snapshot = Snapshot()
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
        next.proxyClient = values["proxy_client"] as? String ?? "unknown"
        next.systemProxyState = values["system_proxy_state"] as? String ?? ""
        next.systemProxyEndpoint = values["system_proxy_endpoint"] as? String ?? ""
        next.systemProxyType = values["system_proxy_type"] as? String ?? ""
        next.automaticControlEnabled = values["automatic_control_enabled"] as? Bool ?? false
        next.tunnelRecoveryEnabled = values["tunnel_recovery_enabled"] as? Bool ?? false
        if let bytes = try? Data(contentsOf: base.appendingPathComponent("config.json")),
           let config = (try? JSONSerialization.jsonObject(with: bytes)) as? [String:Any] {
            next.automaticControlEnabled = config["automatic_control_enabled"] as? Bool ?? false
            next.tunnelRecoveryEnabled = config["tunnel_recovery_enabled"] as? Bool ?? false
        }
        next.deepConnection = values["deep_connection_diagnostics"] as? [String:Any] ?? [:]
        next.codexStream = values["codex_stream_diagnostics"] as? [String:Any] ?? [:]
        next.uploadProbe = values["upload_probe"] as? [String:Any] ?? [:]
        next.uploadNodeHistory = values["upload_node_history"] as? [[String:Any]] ?? []
        next.uploadAdvice = values["upload_recommendation"] as? [String:Any] ?? [:]
        next.shadowrocketNode = values["shadowrocket_node"] as? [String:Any] ?? [:]
        next.workflowHealth = values["workflow_health"] as? [String:Any] ?? [:]
        next.computerUseObservation = values["computer_use_observation"] as? [String:Any] ?? [:]
        next.clientEventCorrelation = values["client_event_correlation"] as? [String:Any] ?? [:]
        next.workflowTimeline = values["workflow_timeline"] as? [String:Any] ?? [:]
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
        next.backendEvidenceSource = values["openai_group_backend_source"] as? String ?? ""
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
        rebuildMenu()
        if dashboardWindow?.isVisible == true { refreshDashboard() }
    }

    private func refreshNode() {
        // Never read Shadowrocket's protected private preferences. Guardian
        // already supplies a scope-labelled global observation; not GPT route proof.
        liveNode = nil
    }

    private var nodePending: Bool {
        if snapshot.proxyClient != "shadowrocket" ||
            snapshot.routeManagement == "native_fallback" ||
            snapshot.routeManagement == "shadowrocket_policy_unverified" { return false }
        guard let liveNode, !liveNode.isEmpty else { return false }
        return liveNode != snapshot.checkedNode
    }
    private var nodeUnverified: Bool {
        // Private global-node reading has been retired. Missing an unrelated
        // provider selection is never a connection fault or amber status.
        return false
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
        guard snapshot.proxyClient == "shadowrocket" else { return "不适用" }
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

    private var networkReviewPending: Bool {
        snapshot.fresh && (snapshot.workflowHealth["network"] as? [String:Any])?["state"] as? String == "partial"
    }

    private func sampleClock(_ timestamp: Int) -> String {
        guard timestamp > 0 else { return "无采样" }
        return DateFormatter.localizedString(from: Date(timeIntervalSince1970: TimeInterval(timestamp)),
                                              dateStyle: .none, timeStyle: .short)
    }

    private var headline: String {
        if guardianPaused { return "守护已暂停" }
        if !guardianRunning { return "守护服务未运行" }
        if !snapshot.fresh { return "等待最新检测" }
        if snapshot.overall == "unknown" { return "系统代理路由待确认" }
        if nodePending { return "节点已切换，等待检测" }
        if networkReviewPending { return "公共入口偶发超时 · 正在复核" }
        if !snapshot.networkHealthy && recoveryBlocked { return "自动恢复受阻 · 需要处理" }
        if !snapshot.networkHealthy { return "代理链路异常" }
        if nodeUnverified { return "基础网络可达 · 节点未核实" }
        if snapshot.business == "attention" { return "网络正常 · 有客户端提示" }
        return "网络基础链路正常"
    }

    private var detail: String {
        if guardianPaused { return "监控已暂停 · 当前代理未受影响" }
        if !guardianRunning { return "后台守护未运行，无法读取实时诊断" }
        if !snapshot.fresh { return "没有足够新的健康检测记录" }
        if snapshot.overall == "unknown" {
            return "当前系统代理可能使用 PAC 或自动发现，不能假定 ChatGPT 失败"
        }
        if nodePending { return "节点名称已同步，新节点的链路健康尚未确认" }
        if networkReviewPending { return "已记录一次真实探测超时，等待再次检测；尚未确认持续故障" }
        if !snapshot.networkHealthy && recoveryBlocked {
            return snapshot.recoveryReason.isEmpty ? "节点切换未成功，请核查 Shadowrocket" :
                snapshot.recoveryReason
        }
        if !snapshot.networkHealthy { return "公共入口不可达 · 等待有界恢复检查" }
        if snapshot.business == "attention" { return "公共入口正常 · 客户端日志有待核实事件" }
        if nodeUnverified { return "Shadowrocket 节点名读取受限；链路仍在独立监测" }
        if snapshot.proxyClient == "system_proxy" {
            return "系统代理 \(snapshot.systemProxyEndpoint) · 公开入口实际探测"
        }
        if snapshot.proxyClient == "system_route" {
            return "未配置显式系统代理 · 检测当前直连或 TUN 出站"
        }
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
        if snapshot.overall == "unknown" { return "路由待确认" }
        if nodePending { return "检测中" }
        if networkReviewPending { return "复核中" }
        if !snapshot.networkHealthy && recoveryBlocked { return "需人工处理" }
        if !snapshot.networkHealthy { return "连接异常" }
        if snapshot.business == "attention" { return "需留意" }
        if nodeUnverified { return "节点未核实" }
        return "基础正常"
    }

    private var menuBarStateMarker: String {
        if !snapshot.fresh || guardianPaused || !guardianRunning { return "○" }
        if snapshot.overall == "unknown" { return "○" }
        if nodePending { return "◐" }
        if networkReviewPending { return "◐" }
        if !snapshot.networkHealthy || snapshot.business == "attention" { return "!" }
        if nodeUnverified { return "?" }
        return "●"
    }

    private var accent: NSColor {
        if guardianPaused || !guardianRunning || !snapshot.fresh { return .secondaryLabelColor }
        if nodePending || networkReviewPending || snapshot.business == "attention" || nodeUnverified { return .systemOrange }
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
        let v = NSView(frame: NSRect(x: 0, y: 0, width: w, height: 294))
        v.addSubview(label("T U N N E L   S E N T I N E L",
                           font: .systemFont(ofSize: 10, weight: .bold),
                           color: .tertiaryLabelColor,
                           frame: NSRect(x: 20, y: 266, width: w - 140, height: 19)))
        v.addSubview(badge(statusLabel, color: accent,
                           frame: NSRect(x: w - 98, y: 263, width: 78, height: 22)))
        v.addSubview(label(headline, font: .systemFont(ofSize: 19, weight: .semibold),
                           color: .labelColor, frame: NSRect(x: 20, y: 229, width: w - 40, height: 27)))
        v.addSubview(label(detail, font: .systemFont(ofSize: 11.5),
                           color: .secondaryLabelColor, frame: NSRect(x: 20, y: 206, width: w - 40, height: 19)))

        let nodeBox = AppearanceFillView(frame: NSRect(x: 18, y: 94, width: w - 36, height: 104),
                                         color: .clear, cornerRadius: 10, surface: .menu)
        let hasRequestRoute = snapshot.fresh && snapshot.backendVerified &&
            !snapshot.actualBackendName.isEmpty && !snapshot.backendObservedAt.isEmpty
        nodeBox.addSubview(label(hasRequestRoute ? "最近 OpenAI 路由记录" : "公开测试请求出口",
                                font: .systemFont(ofSize: 10, weight: .medium),
                                color: .secondaryLabelColor,
                                frame: NSRect(x: 12, y: 84, width: nodeBox.bounds.width - 24, height: 15)))
        nodeBox.addSubview(label(hasRequestRoute ? snapshot.actualBackendName : observedEgress,
                                font: .systemFont(ofSize: 13.5, weight: .semibold),
                                color: .labelColor,
                                frame: NSRect(x: 12, y: 57, width: nodeBox.bounds.width - 24, height: 22)))
        nodeBox.addSubview(label(hasRequestRoute ? "公开测试请求出口" : "节点控制",
                                font: .systemFont(ofSize: 10, weight: .medium),
                                color: .secondaryLabelColor,
                                frame: NSRect(x: 12, y: 35, width: nodeBox.bounds.width - 24, height: 15)))
        nodeBox.addSubview(label(hasRequestRoute ? observedEgress :
                                 snapshot.automaticControlEnabled ? "需独立验证控制能力" : "只读监测 · 不自动换节点",
                                font: .systemFont(ofSize: 13.5, weight: .semibold),
                                color: .labelColor,
                                frame: NSRect(x: 12, y: 9, width: nodeBox.bounds.width - 24, height: 23)))
        v.addSubview(nodeBox)

        divider(88, in: v)
        v.addSubview(label("●", font: .systemFont(ofSize: 13),
                           color: networkReviewPending ? .systemOrange :
                                  snapshot.networkHealthy ? .systemGreen : .systemRed,
                           frame: NSRect(x: 20, y: 64, width: 16, height: 19)))
        v.addSubview(label("基础链路", font: .systemFont(ofSize: 12, weight: .medium), color: .labelColor,
                           frame: NSRect(x: 40, y: 64, width: 126, height: 19)))
        v.addSubview(label(networkReviewPending ? "单次超时 · 复核中" :
                           snapshot.fresh && snapshot.networkHealthy ? "公共入口可达" : "待确认 / 不可达",
                           font: .systemFont(ofSize: 11), color: .secondaryLabelColor,
                           frame: NSRect(x: 164, y: 64, width: w - 184, height: 19), alignment: .right))

        let issueText: String
        if !snapshot.fresh {
            issueText = "无最新日志诊断"
        } else if snapshot.issues.isEmpty {
            issueText = "近 3 分钟未见已识别错误"
        } else {
            issueText = snapshot.issues.prefix(2).map { "\($0.title) ×\($0.count)" }.joined(separator: " · ")
        }
        v.addSubview(label("●", font: .systemFont(ofSize: 13), color: snapshot.issues.isEmpty ? .secondaryLabelColor : .systemOrange,
                           frame: NSRect(x: 20, y: 38, width: 16, height: 19)))
        v.addSubview(label("客户端诊断", font: .systemFont(ofSize: 12, weight: .medium),
                           color: .labelColor, frame: NSRect(x: 40, y: 38, width: 105, height: 19)))
        v.addSubview(label(issueText, font: .systemFont(ofSize: 10.5), color: .secondaryLabelColor,
                           frame: NSRect(x: 139, y: 38, width: w - 159, height: 19), alignment: .right))

        // No divider above the footer: the line belongs to the status block.
        let timeText = snapshot.checkedAt.count >= 19
            ? String(snapshot.checkedAt.dropFirst(11).prefix(8)) : "—"
        let recoveryText = recoveryBlocked && snapshot.recoveryRetrySeconds > 0
            ? " · 恢复重试约 \(snapshot.recoveryRetrySeconds / 60) 分钟后"
            : " · 系统代理监测"
        v.addSubview(label("最近检测 \(timeText)\(recoveryText)",
                           font: .systemFont(ofSize: 10), color: .tertiaryLabelColor,
                           frame: NSRect(x: 20, y: 12, width: w - 40, height: 18)))
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


    private func rebuildMenu() {
        guard let statusItem else { return }
        let fingerprint = [
            headline, detail, liveNode ?? "", snapshot.checkedNode, snapshot.checkedAt,
            snapshot.proxyClient,snapshot.clashMode,snapshot.clashGroup,snapshot.clashParent,
            String(snapshot.automaticControlEnabled),String(snapshot.tunnelRecoveryEnabled),
            String(describing:snapshot.deepConnection),String(describing:snapshot.codexStream),
            String(describing:snapshot.workflowHealth),String(describing:snapshot.computerUseObservation),
            String(describing:snapshot.clientEventCorrelation),
            String(describing:snapshot.workflowTimeline),
            snapshot.clashAutoSwitchMode,snapshot.clashFailoverState,
            snapshot.clashFailoverFrom,snapshot.clashFailoverTo,String(snapshot.clashFailoverActions),
            snapshot.clashSelectedNode,String(snapshot.clashActiveConnections),
            String(snapshot.clashCandidateCount),String(snapshot.clashEligibleCount),
            String(snapshot.fresh), String(snapshot.networkHealthy),
            String(guardianRunning), String(guardianPaused), String(nodeUnverified),
            statusLabel, menuBarStateMarker,
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
            && !snapshot.egressCountry.isEmpty ? " · 公网 \(shortEgress)" : ""
        statusItem.button?.title = "\(menuBarStateMarker) \(statusLabel)\(compactEdge)"
        statusItem.button?.contentTintColor = nil
        let hasRouteEvidence = snapshot.fresh && snapshot.backendVerified &&
            !snapshot.actualBackendName.isEmpty && !snapshot.backendObservedAt.isEmpty
        let selectedDescription = hasRouteEvidence
            ? "最近 OpenAI 域名的请求级路由记录：\(snapshot.actualBackendName)；采样 \(snapshot.backendObservedAt)；来源 \(snapshot.backendEvidenceSource)"
            : "未获取有效的请求级路由数据；公开测试出口不等于实际客户端代理节点"
        let owner = snapshot.proxyClient == "shadowrocket" ? "Shadowrocket" :
                    snapshot.proxyClient == "clash" ? "Mihomo" : "系统"
        let routeNodeDescription = "macOS 当前代理入口（\(owner)）：\(snapshot.systemProxyEndpoint.isEmpty ? "直连 / TUN 或未解析" : snapshot.systemProxyEndpoint)"
        statusItem.button?.toolTip = "TunnelSentinel · \(statusLabel)\n\(headline)\n\(selectedDescription)\nOpenAI 公共出口：\(observedEgress)\n\(routeNodeDescription)\n\(detail)"
        statusItem.button?.setAccessibilityLabel("TunnelSentinel，\(statusLabel)，OpenAI 出口 \(shortEgress)，\(routeNodeDescription)")
        statusItem.button?.setAccessibilityValue("\(headline)；\(detail)")
        let menu = NSMenu()
        let card = NSMenuItem()
        card.view = menuCard()
        menu.addItem(card)
        menu.addItem(.separator())
        menu.addItem(menuItem("打开监控中心…", symbol: "rectangle.grid.1x2", action: #selector(openDashboard)))
        menu.addItem(menuItem("立即检测基础链路", symbol: "arrow.clockwise", action: #selector(forceProbe)))
        menu.addItem(menuItem("立即测上行", symbol: "arrow.up.circle", action: #selector(forceUploadProbe)))
        if snapshot.proxyClient == "shadowrocket" {
            menu.addItem(.separator())
            menu.addItem(switchMenuRow("Shadowrocket 隧道重连",
                                       subtitle: "仅控制已确认由 Shadowrocket 持有的隧道",
                                       on: snapshot.tunnelRecoveryEnabled,
                                       enabled: !configUpdateBusy, tag: 2))
        }
        menu.addItem(.separator())
        menu.addItem(menuItem("退出菜单栏", symbol: "xmark.circle", action: #selector(quitMenu)))
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
        requestProbe()
        refreshStatus()
        refreshNode()
    }

    /// Drop a one-shot flag the background guardian consumes on its next cycle.
    @objc private func forceUploadProbe() {
        let dir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/OpenAILinkGuardian")
        let flag = dir.appendingPathComponent("upload_probe.request")
        do {
            try "requested-by-menu".write(to: flag, atomically: true, encoding: .utf8)
        } catch {
            showError("无法请求上行测速：\(error.localizedDescription)")
        }
    }

    private func showError(_ text: String) {
        let alert = NSAlert()
        alert.messageText = "TunnelSentinel 无法完成操作"
        alert.informativeText = text
        alert.alertStyle = .warning
        alert.runModal()
    }

    // One-shot Codex/Work environment action. Independent of proxy groups and
    // of Guardian's node/automatic failover; never restarts ChatGPT or Codex.
    private func codexProxyEnvStatus() -> String {
        // Protocol compatibility is explicit: SOCKS/PAC cannot silently be
        // converted to HTTP_PROXY. Existing managed values remain untouched.
        if snapshot.systemProxyState == "pac_unresolved" {
            return "PAC 需逐目标解析 · 暂不自动同步"
        }
        if snapshot.systemProxyType == "socks" {
            return "SOCKS5 已识别 · Codex 环境待人工核对"
        }
        if snapshot.systemProxyState == "direct_or_tun" {
            return "直连 / TUN · 无显式 HTTP 代理"
        }
        let path = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".codex/.env")
        guard let raw = try? String(contentsOf: path, encoding: .utf8) else {
            return "未配置"
        }
        guard raw.contains("# >>> CHATGPT_PROXY_MANAGED_BEGIN >>>"),
              raw.contains("# <<< CHATGPT_PROXY_MANAGED_END <<<") else {
            return "未托管"
        }
        let port = raw.components(separatedBy: "\n").first(where: {
            $0.hasPrefix("HTTP_PROXY=")
        })?.replacingOccurrences(of: "HTTP_PROXY=", with: "")
          .replacingOccurrences(of: "\"", with: "") ?? ""
        guard port.hasPrefix("http://127.0.0.1:") else { return "配置待核实" }
        let current = "http://" + snapshot.systemProxyEndpoint
        return current == port ? "已同步 · " + port.replacingOccurrences(of: "http://", with: "")
            : "待同步 · " + port.replacingOccurrences(of: "http://", with: "")
    }

    @objc private func syncCodexProxyEnv(_ sender: NSButton) {
        guard !codexProxyEnvBusy else { return }
        let alert = NSAlert()
        alert.messageText = "同步 Codex 代理入口"
        alert.informativeText = "只把当前 macOS 正在使用、通过 HTTPS 公开检测的本机 HTTP 代理写入 ~/.codex/.env。先备份，再更新托管区块；不改系统代理、不切节点、不重启 ChatGPT。新进程需完全退出重开才会使用新的环境。"
        alert.addButton(withTitle: "检测并同步")
        alert.addButton(withTitle: "取消")
        guard alert.runModal() == .alertFirstButtonReturn else { return }
        runCodexProxyEnvAction("sync")
    }

    @objc private func rollbackCodexProxyEnv(_ sender: NSButton) {
        guard !codexProxyEnvBusy else { return }
        let alert = NSAlert()
        alert.messageText = "撤销 Codex 托管代理设置"
        alert.informativeText = "仅移除桌面脚本与 TunnelSentinel 共同管理的代理区块。不会删除其他 .env 内容；也不会关闭正在运行的 ChatGPT 或更改系统代理。"
        alert.addButton(withTitle: "撤销托管配置")
        alert.addButton(withTitle: "取消")
        guard alert.runModal() == .alertFirstButtonReturn else { return }
        runCodexProxyEnvAction("rollback")
    }

    private func runCodexProxyEnvAction(_ action: String) {
        guard action == "sync" || action == "rollback" else { return }
        let script = base.appendingPathComponent("codex_proxy_env.py")
        guard FileManager.default.fileExists(atPath: script.path) else {
            showError("找不到随 TunnelSentinel 安装的 Codex 代理入口工具。")
            return
        }
        codexProxyEnvBusy = true
        refreshDashboard()
        DispatchQueue.global(qos: .utility).async { [weak self] in
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
            process.arguments = [script.path, action]
            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = Pipe()
            var code: Int32 = -1
            var response = ""
            do {
                try process.run()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                process.waitUntilExit()
                code = process.terminationStatus
                response = String(decoding: data, as: UTF8.self)
            } catch { response = error.localizedDescription }
            let parsed = (try? JSONSerialization.jsonObject(with: Data(response.utf8))) as? [String:Any]
            let result = parsed?["state"] as? String ?? ""
            let reason = parsed?["reason"] as? String ?? ""
            DispatchQueue.main.async { [weak self] in
                guard let self else { return }
                self.codexProxyEnvBusy = false
                self.refreshDashboard()
                if code != 0 || result == "refused" || result.isEmpty {
                    self.showError(reason.isEmpty ? "代理入口操作未完成，已保持原配置。" : reason)
                    return
                }
                let notice = NSAlert()
                notice.messageText = action == "sync" ? "Codex 代理入口已处理" : "托管配置已撤销"
                notice.informativeText = action == "sync"
                    ? (result == "unchanged" ? "当前入口已一致，无需重写 .env。" :
                       "已更新并备份 .env。请在合适时完全退出并重新打开 ChatGPT/Codex，当前会话不会被中断。")
                    : (result == "not_managed" ? "没有发现可撤销的托管区块。" :
                       "已保留 .env 的其他内容。需要完全退出并重新打开客户端才会使用新环境。")
                notice.addButton(withTitle: "知道了")
                notice.runModal()
            }
        }
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

    @objc private func openLog() { presentDashboard(tab: 1) }

    private func recoveryEnabled() -> Bool {
        let path = base.appendingPathComponent("config.json")
        guard let data = try? Data(contentsOf: path),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return false }
        return json["codex_auto_failover_enabled"] as? Bool == true
    }

    // All slow disk/service work must stay off the AppKit main thread.
    // The Guardian needs a service restart to load this config; never wait
    // synchronously for launchctl from a slider's action callback.
    private func updateMonitorConfig(_ changes: [String: Bool], disarmFailovers: Bool = false) {
        guard !configUpdateBusy else { return }
        configUpdateBusy = true
        let path = base.appendingPathComponent("config.json")
        let service = "gui/\(getuid())/\(guardianLabel)"
        // Optimistic UI display; the saved config remains the source of truth.
        if let enabled = changes["automatic_control_enabled"] { snapshot.automaticControlEnabled = enabled }
        if let enabled = changes["tunnel_recovery_enabled"] { snapshot.tunnelRecoveryEnabled = enabled }
        // Do not replace NSMenu contents reentrantly during its switch event.
        DispatchQueue.main.async { [weak self] in
            self?.lastRenderedState = ""
            self?.rebuildMenu()
            self?.refreshDashboard()
        }
        DispatchQueue.global(qos: .utility).async { [weak self] in
            var errorText: String?
            do {
                guard let source = try? Data(contentsOf: path),
                      var settings = (try? JSONSerialization.jsonObject(with: source)) as? [String:Any]
                else { throw NSError(domain: "TunnelSentinel", code: 1) }
                for (key,value) in changes { settings[key] = value }
                if disarmFailovers {
                    settings["codex_auto_failover_enabled"] = false
                    settings["clash_auto_failover_enabled"] = false
                    settings["codex_auto_preflight_enabled"] = false
                }
                let payload = try JSONSerialization.data(withJSONObject: settings,
                                                          options: [.prettyPrinted,.sortedKeys])
                try payload.write(to: path, options: .atomic)
                let process = Process()
                process.executableURL = URL(fileURLWithPath: "/bin/launchctl")
                process.arguments = ["kickstart", "-k", service]
                process.standardOutput = FileHandle.nullDevice
                process.standardError = FileHandle.nullDevice
                try process.run()
                // Bounded wait on utility queue. A hung launchctl cannot hang UI.
                let limit = Date().addingTimeInterval(8)
                while process.isRunning && Date() < limit {
                    Thread.sleep(forTimeInterval: 0.05)
                }
                if process.isRunning {
                    process.terminate()
                    errorText = "配置已保存，但守护进程重载超时。请检查后台服务。"
                } else if process.terminationStatus != 0 {
                    errorText = "配置已保存，但守护进程重载失败。"
                }
            } catch {
                errorText = "设置更新未完成。请检查监控配置文件。"
            }
            DispatchQueue.main.async { [weak self] in
                guard let self else { return }
                self.configUpdateBusy = false
                if let errorText { self.showError(errorText) }
                self.lastRenderedState = ""
                self.refreshStatus()
            }
        }
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
        updateMonitorConfig(["automatic_control_enabled": enabled], disarmFailovers: !enabled)
    }

    @objc private func toggleTunnelRecovery() {
        let enabled = !snapshot.tunnelRecoveryEnabled
        updateMonitorConfig(["tunnel_recovery_enabled": enabled])
    }

    @objc private func showDeepConnection() { presentDashboard(tab: 1) }

    // The menu stays deliberately short. Native switches remain real controls,
    // not menu-item text pretending to be a toggle.
    private var autoSwitchSupported: Bool {
        snapshot.fresh && snapshot.routeManagement == "clash_observe_only" &&
            snapshot.clashGroup == "TunnelSentinel-OpenAI" && snapshot.clashGroupType == "Selector"
    }

    private func switchMenuRow(_ title: String, subtitle: String,
                               on: Bool, enabled: Bool, tag: Int) -> NSMenuItem {
        let row = NSView(frame: NSRect(x: 0, y: 0, width: 340, height: 52))
        row.addSubview(label(title, font: .systemFont(ofSize: 12.5, weight: .medium),
                             color: .labelColor, frame: NSRect(x: 20, y: 26, width: 247, height: 18)))
        row.addSubview(label(subtitle, font: .systemFont(ofSize: 10),
                             color: .secondaryLabelColor, frame: NSRect(x: 20, y: 8, width: 247, height: 15)))
        let control = NSSwitch(frame: NSRect(x: 284, y: 14, width: 43, height: 25))
        control.state = on ? .on : .off
        control.isEnabled = enabled
        control.tag = tag
        control.target = self
        control.action = #selector(switchChanged(_:))
        control.toolTip = enabled ? title : "该代理尚无已验证的自动控制方式，仅提供安全监测"
        row.addSubview(control)
        let item = NSMenuItem()
        item.view = row
        return item
    }

    @objc private func switchChanged(_ sender: NSSwitch) {
        if configUpdateBusy {
            sender.state = (sender.tag == 1 ? snapshot.automaticControlEnabled : snapshot.tunnelRecoveryEnabled) ? .on : .off
            return
        }
        if sender.tag == 1 {
            guard autoSwitchSupported else { sender.state = .off; return }
            toggleAutomaticControl()
        } else if sender.tag == 2 {
            toggleTunnelRecovery()
        }
    }

    @objc private func openDashboard() { presentDashboard(tab: 0) }
    @objc private func dashboardTabChanged(_ sender: NSSegmentedControl) {
        dashboardSelection = sender.selectedSegment
        refreshDashboard()
        dashboardScroll?.contentView.scroll(to: .zero)
        if let scroll = dashboardScroll { scroll.reflectScrolledClipView(scroll.contentView) }
    }
    private func presentDashboard(tab: Int) {
        dashboardSelection = tab
        if let existing = dashboardWindow {
            dashboardTabs?.selectedSegment = tab
            refreshDashboard()
            dashboardScroll?.contentView.scroll(to: .zero)
            if let scroll = dashboardScroll { scroll.reflectScrolledClipView(scroll.contentView) }
            existing.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
            return
        }
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 620, height: 640),
                              styleMask: [.titled, .closable, .miniaturizable],
                              backing: .buffered, defer: false)
        window.title = "TunnelSentinel · 监控中心"
        window.isReleasedWhenClosed = false
        window.center()
        guard let root = window.contentView else { return }
        let background = NSVisualEffectView(frame: root.bounds)
        background.material = .windowBackground
        background.blendingMode = .withinWindow
        background.autoresizingMask = [.width, .height]
        root.addSubview(background)
        background.addSubview(label("工作流监控", font: .systemFont(ofSize: 23, weight: .semibold),
                                    color: .labelColor, frame: NSRect(x: 28, y: 578, width: 330, height: 31)))
        background.addSubview(label("ChatGPT · Codex · Computer Use", font: .systemFont(ofSize: 11.5),
                                    color: .secondaryLabelColor, frame: NSRect(x: 28, y: 556, width: 440, height: 18)))
        let tabs = NSSegmentedControl(labels: ["总览", "记录", "设置"],
                                      trackingMode: .selectOne,
                                      target: self, action: #selector(dashboardTabChanged(_:)))
        tabs.frame = NSRect(x: 27, y: 510, width: 566, height: 32)
        tabs.selectedSegment = tab
        background.addSubview(tabs)
        dashboardTabs = tabs
        let scroll = NSScrollView(frame: NSRect(x: 27, y: 32, width: 568, height: 463))
        scroll.scrollerStyle = .overlay
        scroll.hasVerticalScroller = true
        scroll.autohidesScrollers = true
        scroll.drawsBackground = false
        background.addSubview(scroll)
        dashboardScroll = scroll
        background.addSubview(label("网络层检测不是 ChatGPT 登录或 Computer Use 功能测试。",
                                    font: .systemFont(ofSize: 10.5),
                                    color: .tertiaryLabelColor,
                                    frame: NSRect(x: 29, y: 11, width: 560, height: 15)))
        dashboardWindow = window
        refreshDashboard()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    private func dashboardHeading(_ title: String, in doc: NSView, y: inout CGFloat) {
        doc.addSubview(label(title, font: .systemFont(ofSize: 13.5, weight: .semibold),
                             color: .labelColor, frame: NSRect(x: 8, y: y, width: 500, height: 22)))
        y += 31
    }

    private func dashboardCompactRow(_ title: String, value: String,
                                     in doc: NSView, y: inout CGFloat) {
        doc.addSubview(label(title, font: .systemFont(ofSize: 12, weight: .medium),
                             color: .secondaryLabelColor,
                             frame: NSRect(x: 13, y: y + 6, width: 215, height: 20)))
        doc.addSubview(label(value, font: .systemFont(ofSize: 12, weight: .semibold),
                             color: .labelColor,
                             frame: NSRect(x: 213, y: y + 6, width: 323, height: 20),
                             alignment: .right))
        doc.addSubview(AppearanceFillView(frame: NSRect(x: 13, y: y + 34, width: 522, height: 1),
                                          color: .separatorColor.withAlphaComponent(0.23)))
        y += 39
    }

    private func dashboardRow(_ title: String, explanation: String, value: String,
                              tone: NSColor = .secondaryLabelColor,
                              in doc: NSView, y: inout CGFloat) {
        let card = AppearanceFillView(frame: NSRect(x: 3, y: y, width: 550, height: 64),
                                      color: .clear, cornerRadius: 9, surface: .row)
        card.addSubview(label(title, font: .systemFont(ofSize: 12.5, weight: .medium),
                              color: .labelColor, frame: NSRect(x: 14, y: 33, width: 312, height: 19)))
        card.addSubview(label(explanation, font: .systemFont(ofSize: 10.5),
                              color: .secondaryLabelColor,
                              frame: NSRect(x: 14, y: 12, width: 520, height: 18)))
        card.addSubview(label(value, font: .systemFont(ofSize: 11.5, weight: .semibold),
                              color: tone, frame: NSRect(x: 328, y: 33, width: 207, height: 19),
                              alignment: .right))
        doc.addSubview(card)
        y += 73
    }

    private func dashboardNote(_ content: String, in doc: NSView, y: inout CGFloat) {
        let note = NSTextField(wrappingLabelWithString: content)
        note.font = .systemFont(ofSize: 11)
        note.textColor = .secondaryLabelColor
        note.frame = NSRect(x: 10, y: y, width: 535, height: 43)
        note.maximumNumberOfLines = 3
        doc.addSubview(note)
        y += 53
    }

    private func dashboardSwitch(_ title: String, description: String,
                                 isOn: Bool, canEdit: Bool, tag: Int,
                                 in doc: NSView, y: inout CGFloat) {
        let card = AppearanceFillView(frame: NSRect(x: 3, y: y, width: 550, height: 72),
                                      color: .clear, cornerRadius: 9, surface: .row)
        card.addSubview(label(title, font: .systemFont(ofSize: 13, weight: .medium),
                              color: .labelColor, frame: NSRect(x: 15, y: 38, width: 418, height: 20)))
        card.addSubview(label(description, font: .systemFont(ofSize: 10.5),
                              color: .secondaryLabelColor,
                              frame: NSRect(x: 15, y: 14, width: 458, height: 18)))
        let control = NSSwitch(frame: NSRect(x: 489, y: 26, width: 46, height: 28))
        control.tag = tag
        control.target = self
        control.action = #selector(switchChanged(_:))
        control.state = isOn ? .on : .off
        control.isEnabled = canEdit
        card.addSubview(control)
        doc.addSubview(card)
        y += 83
    }

    private func workflowCard(_ key: String, title: String,
                              in doc: NSView, y: inout CGFloat) {
        let axis = snapshot.workflowHealth[key] as? [String:Any] ?? [:]
        let state = snapshot.fresh ? (axis["state"] as? String ?? "unknown") : "unknown"
        let display: (String, NSColor)
        switch state {
        case "ok": display = ("基础连通正常", .systemGreen)
        case "partial": display = ("部分证据", .systemBlue)
        case "degraded": display = ("出现异常", .systemOrange)
        case "failed": display = ("连接失败", .systemRed)
        default: display = ("尚未验证", .secondaryLabelColor)
        }
        let caption = snapshot.fresh ? (axis["label"] as? String ?? "缺少可用的业务证据") : "监控快照已过期，等待新采样"
        dashboardRow(title, explanation: caption,
                     value: display.0, tone: display.1, in: doc, y: &y)
    }


    private func dashboardTwoLine(_ value: String, frame: NSRect) -> NSTextField {
        let field = NSTextField(wrappingLabelWithString: value)
        field.font = .systemFont(ofSize: 11)
        field.textColor = .secondaryLabelColor
        field.maximumNumberOfLines = 2
        field.lineBreakMode = .byTruncatingTail
        field.frame = frame
        return field
    }

    private func statusColor(_ state: String) -> NSColor {
        switch state {
        case "ok": return .systemGreen
        case "partial": return .systemBlue
        case "failed": return .systemRed
        case "degraded": return .systemOrange
        default: return .secondaryLabelColor
        }
    }

    private func statusText(_ state: String) -> String {
        switch state {
        case "ok": return "基础正常"
        case "partial": return "部分已验证"
        case "failed": return "连接失败"
        case "degraded": return "需要关注"
        default: return "尚未验证"
        }
    }

    private func axisData(_ key: String) -> (String, String) {
        let axis = snapshot.workflowHealth[key] as? [String:Any] ?? [:]
        let state = snapshot.fresh ? (axis["state"] as? String ?? "unknown") : "unknown"
        let detail = snapshot.fresh
            ? (axis["label"] as? String ?? "暂无新鲜业务证据")
            : "上次检测已过期"
        return (state, detail)
    }

    private func overviewHero(in doc: NSView, y: inout CGFloat) {
        let network = axisData("network").0
        let codex = axisData("codex").0
        let browser = axisData("computer_use").0
        let bad = [network,codex,browser].contains("failed") ||
                  [network,codex,browser].contains("degraded")
        let chatgpt = axisData("chatgpt").0
        let title: String
        if browser == "failed" || browser == "degraded" {
            title = "Computer Use 需要关注"
        } else if codex == "failed" || codex == "degraded" {
            title = "Codex 连接需要关注"
        } else if network == "failed" || network == "degraded" {
            title = "基础网络需要关注"
        } else if chatgpt == "degraded" || chatgpt == "failed" {
            title = "ChatGPT 入口需要关注"
        } else if browser == "partial" {
            title = "Computer Use 服务在线 · 任务未验"
        } else if network == "ok" {
            title = "网络可达 · 业务结果待核实"
        } else {
            title = "关键工作流状态待确认"
        }
        let subtitle = "优先关注 Computer Use、Codex、ChatGPT；网络用于定位故障"
        let tone: NSColor = bad ? .systemOrange :
                            network == "ok" ? .systemBlue : .secondaryLabelColor
        let header = AppearanceFillView(frame: NSRect(x: 3, y: y, width: 550, height: 84),
                                        color: .clear, cornerRadius: 13, surface: .hero)
        header.addSubview(AppearanceFillView(frame: NSRect(x: 19, y: 49, width: 9, height: 9),
                                            color: tone, cornerRadius: 4.5))
        header.addSubview(label(title, font: .systemFont(ofSize: 20, weight: .semibold),
                                color: .labelColor,
                                frame: NSRect(x: 37, y: 39, width: 475, height: 30)))
        header.addSubview(label(subtitle, font: .systemFont(ofSize: 11.5),
                                color: .secondaryLabelColor,
                                frame: NSRect(x: 20, y: 12, width: 508, height: 20)))
        doc.addSubview(header)
        y += 95
    }

    private func dashboardHealthTile(_ key: String, title: String, symbol: String,
                                     x: CGFloat, y: CGFloat, in doc: NSView) {
        let (state, detail) = axisData(key)
        let card = NSView(frame: NSRect(x: x, y: y, width: 267, height: 84))
        let image = NSImageView(frame: NSRect(x: 16, y: 59, width: 17, height: 18))
        image.image = NSImage(systemSymbolName: symbol, accessibilityDescription: title)
        image.contentTintColor = .secondaryLabelColor
        card.addSubview(image)
        card.addSubview(label(title, font: .systemFont(ofSize: 12.5, weight: .medium),
                              color: .labelColor, frame: NSRect(x: 42, y: 58, width: 135, height: 20)))
        let evidence = snapshot.workflowHealth[key] as? [String:Any] ?? [:]
        let observation = evidence["observed_at"] as? Int ?? 0
        let stamp = observation > 0 ? "测于 \(sampleClock(observation))" : "尚无采样"
        card.addSubview(label(stamp, font: .systemFont(ofSize: 10),
                              color: .secondaryLabelColor,
                              frame: NSRect(x: 172, y: 60, width: 83, height: 17),
                              alignment: .right))
        let dot = AppearanceFillView(frame: NSRect(x: 16, y: 37, width: 7, height: 7),
                                     color: statusColor(state), cornerRadius: 3.5)
        card.addSubview(dot)
        let evidenceSource = evidence["source"] as? String ?? ""
        let displayStatus = state == "partial" && key == "computer_use"
            ? (evidenceSource == "local_codex_cua_tool_status" ? "已观察到工具调用" : "控制服务在线")
            : state == "partial" && key == "codex" ? "请求有记录 · 生成未验"
            : state == "partial" && key == "chatgpt" ? "公开入口可达" : statusText(state)
        card.addSubview(label(displayStatus, font: .systemFont(ofSize: 12, weight: .semibold),
                              color: statusColor(state), frame: NSRect(x: 29, y: 32, width: 222, height: 21)))
        card.addSubview(dashboardTwoLine(detail, frame: NSRect(x: 16, y: 6, width: 237, height: 26)))
        doc.addSubview(card)
    }

    @objc private func openTimelineFromOverview(_ sender: NSButton) {
        dashboardSelection = 1
        dashboardTabs?.selectedSegment = 1
        dashboardScroll?.contentView.scroll(to: .zero)
        refreshDashboard()
    }

    @objc private func toggleTimelineDetails(_ sender: NSButton) {
        guard sender.tag >= 0 && sender.tag < timelineVisibleIDs.count else { return }
        let id = timelineVisibleIDs[sender.tag]
        if expandedTimelineEvents.contains(id) {
            expandedTimelineEvents.remove(id)
        } else {
            expandedTimelineEvents.insert(id)
        }
        refreshDashboard()
    }

    private func readableEventSource(_ source: String) -> String {
        switch source {
        case "codex_remote_control_read_only_sqlite": return "Codex 真实连接日志"
        case "codex_read_only_sqlite", "codex_client_read_only_sqlite": return "Codex 客户端日志"
        case "client_log_classifier": return "客户端异常日志"
        case "macos_system_proxy": return "macOS 系统代理"
        case "public_trace_two_sample_confirmation": return "公网出口检测"
        default: return "TunnelSentinel 监控记录"
        }
    }

    private func eventID(_ event: [String:Any]) -> String {
        String(event["kind"] as? String ?? "event") + ":" + String(event["at"] as? Int ?? 0)
    }

    private func timelineEventCard(_ event: [String:Any],
                                   in doc: NSView, y: inout CGFloat) {
        let kind = event["kind"] as? String ?? ""
        let remote = kind == "codex_remote_session"
        let recovered = (event["reconnected_at"] as? Int ?? 0) > 0
        let warning = (event["level"] as? String) == "warning"
        let accent: NSColor = remote ? (recovered ? .systemGreen : .systemOrange) :
                               warning ? .systemOrange : .secondaryLabelColor
        let started = event["at"] as? Int ?? 0
        let time = Date(timeIntervalSince1970: TimeInterval(started))
        let stamp = DateFormatter.localizedString(from: time, dateStyle: .none, timeStyle: .short)
        let titleText = remote ? "Codex 远程控制" :
                       (event["title"] as? String ?? "连接状态变化")
        let duration = event["duration_seconds"] as? Int ?? 0
        let attempts = event["retries"] as? Int ?? 0
        let failures = event["connect_failures"] as? Int ?? 0
        let value = remote ? (recovered ? "\(duration) 秒后恢复" : "仍在重新连接") :
                    warning ? "需要关注" : "已记录"
        let sub = remote ? (recovered ?
                  "\(stamp) 断开，重试最多 \(max(1,attempts)) 次" :
                  "\(stamp) 检测到断开，尚未看到恢复记录") :
                  "\(stamp) · \(readableEventSource(event["source"] as? String ?? ""))"
        let id = eventID(event)
        let expanded = expandedTimelineEvents.contains(id)
        let height: CGFloat = expanded ? 177 : 115
        let card = AppearanceFillView(frame: NSRect(x: 3, y: y, width: 550, height: height),
                                     color: .clear, cornerRadius: 12, surface: .event)
        // A narrow severity rail is more readable than fully tinted cards.
        card.addSubview(AppearanceFillView(frame: NSRect(x: 0, y: 13, width: 3, height: height-26),
                                          color: accent.withAlphaComponent(0.8), cornerRadius: 1.5))
        card.addSubview(label(titleText, font: .systemFont(ofSize: 13.5, weight: .semibold),
                              color: .labelColor, frame: NSRect(x: 17, y: height-32, width: 330, height: 21)))
        card.addSubview(label(recovered ? "已恢复" : warning ? "待核实" : "观察记录",
                              font: .systemFont(ofSize: 11, weight: .medium), color: accent,
                              frame: NSRect(x: 423, y: height-30, width: 110, height: 20), alignment: .right))
        card.addSubview(label(value, font: .systemFont(ofSize: 17, weight: .semibold),
                              color: .labelColor, frame: NSRect(x: 18, y: height-60, width: 456, height: 24)))
        card.addSubview(label(sub, font: .systemFont(ofSize: 11),
                              color: .secondaryLabelColor, frame: NSRect(x: 18, y: height-80, width: 515, height: 19)))
        let button = NSButton(title: expanded ? "收起详情" : "查看详情", target: self,
                              action: #selector(toggleTimelineDetails(_:)))
        button.isBordered = false
        button.font = .systemFont(ofSize: 11.5, weight: .semibold)
        button.contentTintColor = .systemBlue
        button.frame = NSRect(x: 11, y: height-111, width: 94, height: 24)
        button.tag = timelineVisibleIDs.count
        timelineVisibleIDs.append(id)
        card.addSubview(button)
        if expanded {
            let line = AppearanceFillView(frame: NSRect(x: 18, y: 57, width: 514, height: 1),
                                          color: .separatorColor.withAlphaComponent(0.45))
            card.addSubview(line)
            let extra = remote ?
                "尝试 \(max(1,attempts)) 次 · 握手失败 \(failures) 次 · 仅确认连接恢复" :
                "来源：\(readableEventSource(event["source"] as? String ?? ""))"
            card.addSubview(dashboardTwoLine(extra, frame: NSRect(x: 19, y: 28, width: 511, height: 28)))
            card.addSubview(label("记录来源已脱敏；没有证据证明节点变化导致此次故障。",
                                  font: .systemFont(ofSize: 10), color: .tertiaryLabelColor,
                                  frame: NSRect(x: 19, y: 9, width: 510, height: 17)))
        }
        doc.addSubview(card)
        y += height + 10
    }

    private func refreshDashboard() {
        guard let scroll = dashboardScroll, dashboardWindow != nil else { return }
        let previousY = scroll.contentView.bounds.origin.y
        // The overview also contains a concise connection path; allow scrolling.
        scroll.hasVerticalScroller = true
        let doc = DashboardFlippedView(frame: NSRect(x: 0, y: 0, width: 558, height: 1250))
        var y: CGFloat = 8
        switch dashboardSelection {
        case 0:
            overviewHero(in: doc, y: &y)
            dashboardHeading("关键工作流 · 按优先级", in: doc, y: &y)
            let panel = AppearanceFillView(frame: NSRect(x: 3, y: y, width: 550, height: 168),
                                           color: .clear, cornerRadius: 12, surface: .tile)
            dashboardHealthTile("computer_use", title: "Computer Use", symbol: "macwindow",
                                x: 0, y: 84, in: panel)
            dashboardHealthTile("codex", title: "Codex", symbol: "terminal",
                                x: 282, y: 84, in: panel)
            dashboardHealthTile("chatgpt", title: "ChatGPT", symbol: "bubble.left.and.bubble.right",
                                x: 0, y: 0, in: panel)
            dashboardHealthTile("network", title: "基础网络", symbol: "network",
                                x: 282, y: 0, in: panel)
            panel.addSubview(AppearanceFillView(frame: NSRect(x: 14, y: 83.5, width: 521, height: 1),
                                                color: .separatorColor.withAlphaComponent(0.25)))
            panel.addSubview(AppearanceFillView(frame: NSRect(x: 274, y: 13, width: 1, height: 141),
                                                color: .separatorColor.withAlphaComponent(0.25)))
            doc.addSubview(panel)
            y += 180
            dashboardHeading("当前连接路径", in: doc, y: &y)
            let localEndpoint = snapshot.systemProxyEndpoint
            let owner = snapshot.proxyClient == "shadowrocket" ? "Shadowrocket" :
                        snapshot.proxyClient == "clash" ? "Clash" : "当前系统代理"
            dashboardCompactRow("macOS 代理入口",
                                value: localEndpoint.isEmpty ? "未识别" : owner + " · " + localEndpoint,
                                in: doc, y: &y)
            dashboardCompactRow("Codex / Work 入口", value: codexProxyEnvStatus(), in: doc, y: &y)
            let edge = snapshot.fresh && snapshot.networkHealthy && snapshot.egressObserved
                ? snapshot.egressIP + (snapshot.egressCountry.isEmpty ? "" : " · " + snapshot.egressCountry)
                : "没有有效的公开出口采样"
            dashboardCompactRow("公开测试请求出口", value: edge, in: doc, y: &y)
            // Optional request-level evidence only. No permanent "unknown node"
            // placeholder, no inferred server from public trace or global choice.
            if snapshot.fresh && snapshot.backendVerified &&
               !snapshot.actualBackendName.isEmpty && !snapshot.backendObservedAt.isEmpty {
                dashboardRow("最近 OpenAI 请求路由",
                             explanation: "采样时间：" + snapshot.backendObservedAt +
                                          " · 不代表后续请求的持续选路",
                             value: snapshot.actualBackendName,
                             in: doc, y: &y)
            }
            // 上行带宽 belongs with the connection path: latency and download
            // speed do not predict whether a multi-megabyte request can be sent.
            let uploadKBps = snapshot.uploadProbe["kbps"] as? Double
                          ?? (snapshot.uploadProbe["kbps"] as? NSNumber)?.doubleValue ?? 0
            let uploadState = snapshot.uploadProbe["state"] as? String ?? "off"
            let uploadRunning = (snapshot.uploadProbe["running"] as? Bool) ?? false
            dashboardRow("上行带宽",
                         explanation: uploadRunning
                            ? "正在实测上传速率（约 30 秒）"
                            : "实测上传速率；决定大上下文的 Codex 请求能否按时发完，低延迟不等于高上行",
                         value: uploadRunning ? "测量中…" : (uploadState == "ok"
                            ? String(format: "%.0f KB/s", uploadKBps)
                            : (uploadState == "pending_or_stale" ? "待测" : "未测量")),
                         tone: uploadState == "ok"
                            ? (uploadKBps < 80 ? .systemOrange : .secondaryLabelColor)
                            : .secondaryLabelColor,
                         in: doc, y: &y)
            let uploadButton = NSButton(title: uploadRunning ? "测速中…" : "立即测上行",
                                        target: self, action: #selector(forceUploadProbe))
            uploadButton.bezelStyle = .rounded
            uploadButton.controlSize = .small
            uploadButton.font = .systemFont(ofSize: 11)
            uploadButton.image = NSImage(systemSymbolName: uploadRunning ? "hourglass" : "arrow.up.circle",
                                         accessibilityDescription: nil)
            uploadButton.imagePosition = .imageLeading
            uploadButton.isEnabled = !uploadRunning
            uploadButton.frame = NSRect(x: 11, y: y - 1, width: 132, height: 26)
            uploadButton.toolTip = "立即实测一次上行带宽（约 30 秒）"
            doc.addSubview(uploadButton)
            y += 30
            let streamCounts = snapshot.codexStream["recent_counts"] as? [String:Int] ?? [:]
            let streamErrors = (streamCounts["broken_pipe"] ?? 0) +
                               (streamCounts["websocket_handshake"] ?? 0) +
                               (streamCounts["connection_reset"] ?? 0) +
                               (streamCounts["ws_closed_after_upgrade"] ?? 0)
            let wsDegraded = (snapshot.codexStream["classification"] as? String) == "ws_degraded"
                          || (streamCounts["http_fallbacks"] ?? 0) > 0
            dashboardRow("Codex 响应流",
                         explanation: wsDegraded
                            ? "WebSocket 握手成功后随即断开，Codex 已自动回退 HTTP；与代理节点无关，不据此切换节点"
                            : "最近 210 秒的真实客户端连接错误；不据此自动切换节点",
                         value: (snapshot.codexStream["state"] as? String) == "ok"
                            ? (wsDegraded ? "WS 异常，已回退 HTTP" : "\(streamErrors) 次异常")
                            : "日志未验证",
                         tone: (wsDegraded || streamErrors > 0) ? .systemOrange : .secondaryLabelColor,
                         in: doc, y: &y)
            if !snapshot.uploadNodeHistory.isEmpty {
                dashboardHeading("节点上行排行", in: doc, y: &y)
                if (snapshot.uploadAdvice["state"] as? String) == "switch_recommended" {
                    let country = snapshot.uploadAdvice["country"] as? String ?? ""
                    let colo = snapshot.uploadAdvice["colo"] as? String ?? ""
                    let kbps = (snapshot.uploadAdvice["best_kbps"] as? NSNumber)?.doubleValue ?? 0
                    dashboardRow("建议切换出口",
                                 explanation: "按实测上行排序；切换后自动重新记录。按出口 IP 归档，不是订阅节点名",
                                 value: country + (colo.isEmpty ? "" : " · " + colo)
                                      + String(format: " · %.0f KB/s", kbps),
                                 tone: .systemGreen, in: doc, y: &y)
                }
                for entry in snapshot.uploadNodeHistory.prefix(3) {
                    let country = entry["country"] as? String ?? "?"
                    let colo = entry["colo"] as? String ?? ""
                    let kbps = (entry["kbps"] as? NSNumber)?.doubleValue ?? 0
                    let bestKbps = (entry["best_kbps"] as? NSNumber)?.doubleValue ?? 0
                    let at = entry["at"] as? Int ?? 0
                    let isCurrent = (entry["ip"] as? String ?? "") == snapshot.egressIP
                    var detail = "最近实测 " + sampleClock(at) + " · 出口 "
                               + (entry["ip"] as? String ?? "")
                    if bestKbps > kbps * 1.2 {
                        detail += String(format: " · 历史最好 %.0f KB/s", bestKbps)
                    }
                    let nodeName = entry["node"] as? String ?? ""
                    let title = nodeName.isEmpty
                        ? country + (colo.isEmpty ? "" : " · " + colo)
                        : nodeName
                    dashboardRow((isCurrent ? "当前 · " : "") + title,
                                 explanation: detail,
                                 value: String(format: "%.0f KB/s", kbps),
                                 tone: kbps < 80 ? .systemOrange : .secondaryLabelColor,
                                 in: doc, y: &y)
                }
            }
            dashboardHeading("最近一次连接事件", in: doc, y: &y)
            let allEvents = snapshot.workflowTimeline["events"] as? [[String:Any]] ?? []
            let recent = allEvents.filter { ["codex_remote_session","codex_stream_error","client_log_issue","computer_use_invocation"].contains($0["kind"] as? String ?? "") }
                                  .max { ($0["at"] as? Int ?? 0) < ($1["at"] as? Int ?? 0) }
            let latest = AppearanceFillView(frame: NSRect(x: 3, y: y, width: 550, height: 82),
                                            color: .clear, cornerRadius: 12, surface: .event)
            if let item = recent {
                let isRemote = (item["kind"] as? String) == "codex_remote_session"
                let ended = (item["reconnected_at"] as? Int ?? 0) > 0
                let labelText = isRemote ? (ended ? "Codex 已重新连接" : "Codex 连接中断") :
                                (item["title"] as? String ?? "客户端连接异常")
                latest.addSubview(label(labelText, font: .systemFont(ofSize: 14, weight: .medium),
                                        color: .labelColor, frame: NSRect(x: 17, y: 46, width: 435, height: 25)))
                let summary = isRemote && ended
                    ? "持续 \(item["duration_seconds"] as? Int ?? 0) 秒 · 通过 Codex 客户端日志确认"
                    : "有新的客户端状态记录，详情见记录"
                latest.addSubview(label(summary, font: .systemFont(ofSize: 11.5),
                                        color: .secondaryLabelColor,
                                        frame: NSRect(x: 18, y: 25, width: 504, height: 20)))
            } else {
                latest.addSubview(label("暂无可确认的连接故障", font: .systemFont(ofSize: 14, weight: .medium),
                                        color: .labelColor, frame: NSRect(x: 17, y: 46, width: 440, height: 25)))
                latest.addSubview(label("没有异常日志不等于所有业务都已验证。",
                                        font: .systemFont(ofSize: 11), color: .secondaryLabelColor,
                                        frame: NSRect(x: 18, y: 24, width: 502, height: 19)))
            }
            let go = NSButton(title: "查看记录", target: self,
                              action: #selector(openTimelineFromOverview(_:)))
            go.isBordered = false
            go.font = .systemFont(ofSize: 11.5, weight: .semibold)
            go.contentTintColor = .systemBlue
            go.frame = NSRect(x: 13, y: 6, width: 115, height: 24)
            latest.addSubview(go)
            doc.addSubview(latest)
            y += 88
        case 1:
            dashboardHeading("连接故障与恢复", in: doc, y: &y)
            dashboardNote("每次断线只显示一条记录。点开事件可查看尝试次数和日志依据。", in: doc, y: &y)
            let events = snapshot.workflowTimeline["events"] as? [[String:Any]] ?? []
            let relevant = events.filter {
                ["codex_remote_session","codex_stream_error","client_log_issue",
                 "proxy_owner_changed","public_egress_changed"].contains($0["kind"] as? String ?? "")
            }.sorted { ($0["at"] as? Int ?? 0) > ($1["at"] as? Int ?? 0) }
            let cycles = relevant.filter { $0["kind"] as? String == "codex_remote_session" }
            let ongoing = cycles.filter { ($0["reconnected_at"] as? Int ?? 0) == 0 }
            let recovered = cycles.filter { ($0["reconnected_at"] as? Int ?? 0) > 0 }
            let summary = AppearanceFillView(frame: NSRect(x: 3, y: y, width: 550, height: 85),
                                             color: .clear, cornerRadius: 12, surface: .event)
            summary.addSubview(label("Codex 远程控制", font: .systemFont(ofSize: 13.5, weight: .semibold),
                                     color: .labelColor, frame: NSRect(x: 17, y: 52, width: 300, height: 21)))
            summary.addSubview(label(ongoing.isEmpty ? "未见进行中的重连事件" : "存在进行中的重连记录",
                                     font: .systemFont(ofSize: 11.5),
                                     color: ongoing.isEmpty ? .secondaryLabelColor : .systemOrange,
                                     frame: NSRect(x: 17, y: 29, width: 395, height: 19)))
            summary.addSubview(label("恢复 \(recovered.count) 次",
                                     font: .systemFont(ofSize: 12, weight: .semibold),
                                     color: recovered.isEmpty ? .secondaryLabelColor : .systemGreen,
                                     frame: NSRect(x: 407, y: 50, width: 122, height: 21),
                                     alignment: .right))
            summary.addSubview(label("仅统计本机已观测到的周期", font: .systemFont(ofSize: 10),
                                     color: .tertiaryLabelColor,
                                     frame: NSRect(x: 17, y: 10, width: 479, height: 16)))
            doc.addSubview(summary)
            y += 103
            timelineVisibleIDs.removeAll()
            let limited = Array(relevant.prefix(16))
            if limited.isEmpty {
                dashboardNote("目前没有需要展示的连接中断；正常使用即可，监控会自动记录后续事件。", in: doc, y: &y)
            } else {
                var previousDay = ""
                for event in limited {
                    let at = event["at"] as? Int ?? 0
                    let date = Date(timeIntervalSince1970: TimeInterval(at))
                    let day = Calendar.current.isDateInToday(date) ? "今天" :
                              Calendar.current.isDateInYesterday(date) ? "昨天" :
                              DateFormatter.localizedString(from: date, dateStyle: .medium, timeStyle: .none)
                    if day != previousDay {
                        doc.addSubview(label(day, font: .systemFont(ofSize: 12, weight: .semibold),
                                             color: .secondaryLabelColor,
                                             frame: NSRect(x: 8, y: y, width: 500, height: 21)))
                        y += 28
                        previousDay = day
                    }
                    timelineEventCard(event, in: doc, y: &y)
                }
            }
            dashboardNote("连接恢复不等于模型任务已完成；无法从时间接近推定节点变化导致断线。", in: doc, y: &y)
            dashboardHeading("实际客户端证据", in: doc, y: &y)
            let cua = snapshot.computerUseObservation
            let backend = cua["backend"] as? [String:Any] ?? [:]
            let execution = cua["execution"] as? [String:Any] ?? [:]
            let serviceOnline = snapshot.fresh && (backend["state"] as? String) == "running"
            let callAt = execution["latest_at"] as? Int ?? 0
            let callStatus = execution["latest_status"] as? String ?? ""
            dashboardRow("Computer Use", explanation: callAt > 0 ?
                         "最近本机工具调用：\(sampleClock(callAt)) · 非云端任务证明" :
                         "仅监测本机控制服务状态，无法验证云端操作",
                         value: callAt > 0 ? (callStatus == "completed" ? "本机调用已结束" :
                                              callStatus == "failed" ? "本机调用失败" : "未完成") :
                                           serviceOnline ? "控制服务在线" : "未确认",
                         in: doc, y: &y)
            let client = snapshot.deepConnection["real_codex_client"] as? [String:Any] ?? [:]
            let routes = client["routes"] as? [[String:Any]] ?? []
            let success = routes.filter { ($0["status"] as? Int) == 200 }
                                .reduce(0) { $0 + ($1["count"] as? Int ?? 0) }
            dashboardRow("Codex 实际 HTTP 请求", explanation: "近 30 分钟客户端记录，不代表最终生成成功",
                         value: routes.isEmpty ? "暂无可靠记录" : "\(success) 次 HTTP 200",
                         in: doc, y: &y)
            let overlap = snapshot.clientEventCorrelation
            if snapshot.fresh && (overlap["state"] as? String) == "nearby_events" {
                let gap = overlap["gap_seconds"] as? Int ?? 0
                dashboardRow("本机事件时间接近",
                             explanation: "Codex 流故障与 Computer Use 工具事件时间相近；不能据此认定同一任务、网络原因或云端完成",
                             value: "相距约 \(gap) 秒", in: doc, y: &y)
            }
            dashboardNote("公开测试、服务进程与客户端日志相互独立；只有真正的请求级归属才能确认机场节点。", in: doc, y: &y)
        default:
            dashboardHeading("Codex / Work 代理入口", in: doc, y: &y)
            dashboardRow("运行环境代理", explanation: "~/.codex/.env · 与桌面 .command 脚本兼容",
                         value: codexProxyEnvStatus(), in: doc, y: &y)
            dashboardRow("当前 macOS 代理", explanation: "仅同步实际系统 HTTP 代理，不盲扫其他代理端口",
                         value: snapshot.systemProxyEndpoint.isEmpty ? "尚未识别" : snapshot.systemProxyEndpoint,
                         in: doc, y: &y)
            let syncButton = NSButton(frame: NSRect(x: 4, y: y, width: 246, height: 31))
            syncButton.title = codexProxyEnvBusy ? "代理配置操作中…" : "检测并同步当前代理"
            syncButton.bezelStyle = .rounded
            syncButton.isEnabled = !codexProxyEnvBusy
            syncButton.target = self
            syncButton.action = #selector(syncCodexProxyEnv(_:))
            doc.addSubview(syncButton)
            let undoButton = NSButton(frame: NSRect(x: 272, y: y, width: 246, height: 31))
            undoButton.title = "撤销托管配置"
            undoButton.bezelStyle = .rounded
            undoButton.isEnabled = !codexProxyEnvBusy
            undoButton.target = self
            undoButton.action = #selector(rollbackCodexProxyEnv(_:))
            doc.addSubview(undoButton)
            y += 45
            dashboardNote("写入仅在手动确认后执行；现有 ChatGPT 会话不被中断。更改后请在合适时完全退出重开客户端。", in: doc, y: &y)
            if snapshot.proxyClient == "shadowrocket" {
                dashboardHeading("Shadowrocket 专属功能", in: doc, y: &y)
                dashboardSwitch("隧道掉线重连", description: "只重连已验证的 Shadowrocket 隧道，不切换节点",
                                isOn: snapshot.tunnelRecoveryEnabled,
                                canEdit: !configUpdateBusy,
                                tag: 2, in: doc, y: &y)
            }
        }
        doc.frame = NSRect(x: 0, y: 0, width: 558, height: max(463, y + 18))
        scroll.documentView = doc
        let maxY = max(CGFloat(0), doc.bounds.height - scroll.contentView.bounds.height)
        scroll.contentView.scroll(to: NSPoint(x: 0, y: min(previousY, maxY)))
        scroll.reflectScrolledClipView(scroll.contentView)
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
