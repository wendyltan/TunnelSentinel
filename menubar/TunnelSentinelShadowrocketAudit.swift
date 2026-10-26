import AppKit
import ApplicationServices
import Foundation

/// Explicit, on-demand rule matches from Shadowrocket's own "测试规则" screen.
/// Does not read protected App Group files or inspect subscription credentials.
/// Never runs periodically or changes the selected server, profile, or rules.
enum ShadowrocketRuleAuditor {
    private static let hostnames = ["chatgpt.com", "ws.chatgpt.com", "api.openai.com", "desktop.chat.openai.com"]
    private static func attribute(_ element: AXUIElement, _ key: String) -> AnyObject? {
        var value: CFTypeRef?
        return AXUIElementCopyAttributeValue(element, key as CFString, &value) == .success ? value : nil
    }
    private static func children(_ e: AXUIElement) -> [AXUIElement] {
        attribute(e, kAXChildrenAttribute as String) as? [AXUIElement] ?? []
    }
    private static func desc(_ e: AXUIElement) -> String {
        attribute(e, kAXDescriptionAttribute as String) as? String ?? ""
    }
    private static func role(_ e: AXUIElement) -> String {
        attribute(e, kAXRoleAttribute as String) as? String ?? ""
    }
    private static func find(_ e: AXUIElement, depth: Int = 0,
                             where matches: (AXUIElement) -> Bool) -> AXUIElement? {
        if matches(e) { return e }
        guard depth < 13 else { return nil }
        for child in children(e) {
            if let found = find(child, depth: depth + 1, where: matches) { return found }
        }
        return nil
    }
    private static func texts(_ e: AXUIElement, depth: Int = 0) -> [String] {
        guard depth < 13 else { return [] }
        var output: [String] = []
        if role(e) == "AXStaticText" { output.append(desc(e)) }
        for child in children(e) { output.append(contentsOf: texts(child, depth: depth + 1)) }
        return output
    }
    private static func window(_ app: AXUIElement) -> AXUIElement? {
        (attribute(app, kAXWindowsAttribute as String) as? [AXUIElement])?.first
    }
    private static func press(_ window: AXUIElement, named: String) -> Bool {
        guard let button = find(window, where: { desc($0) == named }) else { return false }
        return AXUIElementPerformAction(button, kAXPressAction as CFString) == .success
    }
    private static func prepare(_ app: AXUIElement) -> AXUIElement? {
        guard var w = window(app) else { return nil }
        if find(w, where: { role($0) == "AXTextField" }) != nil { return w }
        // These are navigation-only presses, not server/profile selections.
        if !press(w, named: "配置") { return nil }
        Thread.sleep(forTimeInterval: 0.25)
        guard let next = window(app) else { return nil }
        w = next
        if find(w, where: { role($0) == "AXTextField" }) != nil { return w }
        if !press(w, named: "测试规则") { return nil }
        Thread.sleep(forTimeInterval: 0.25)
        return window(app)
    }
    static func run() -> [String: Any] {
        let started = Int(Date().timeIntervalSince1970)
        let source = "shadowrocket_native_rule_tester"
        guard AXIsProcessTrusted(),
              let app = NSRunningApplication.runningApplications(withBundleIdentifier: "com.liguangming.Shadowrocket").first
        else { return ["source": source, "checked_at": started, "state": "not_authorized", "rules": []] }
        let previous = NSWorkspace.shared.frontmostApplication
        defer {
            // Do not steal focus if the user switched apps during this audit.
            if NSWorkspace.shared.frontmostApplication?.processIdentifier == app.processIdentifier,
               previous?.processIdentifier != app.processIdentifier { _ = previous?.activate() }
        }
        _ = app.activate()
        Thread.sleep(forTimeInterval: 0.25)
        guard NSWorkspace.shared.frontmostApplication?.processIdentifier == app.processIdentifier
        else { return ["source": source, "checked_at": started, "state": "focus_unavailable", "rules": []] }
        let axApp = AXUIElementCreateApplication(app.processIdentifier)
        guard let w = prepare(axApp),
              let field = find(w, where: { role($0) == "AXTextField" })
        else { return ["source": source, "checked_at": started, "state": "tester_unavailable", "rules": []] }
        var rows = [[String: String]]()
        for hostname in hostnames {
            guard NSWorkspace.shared.frontmostApplication?.processIdentifier == app.processIdentifier
            else { break }
            let set = AXUIElementSetAttributeValue(field, kAXValueAttribute as CFString, hostname as CFTypeRef)
            guard set == .success else { continue }
            let down = CGEvent(keyboardEventSource: nil, virtualKey: 36, keyDown: true)
            let up = CGEvent(keyboardEventSource: nil, virtualKey: 36, keyDown: false)
            down?.post(tap: .cghidEventTap)
            up?.post(tap: .cghidEventTap)
            Thread.sleep(forTimeInterval: 0.32)
            guard let current = window(axApp) else { continue }
            let lines = texts(current)
            let policy = lines.first(where: { $0.hasPrefix("策略, ") })?.replacingOccurrences(of: "策略, ", with: "") ?? ""
            let kind = lines.first(where: { $0.hasPrefix("类型, ") })?.replacingOccurrences(of: "类型, ", with: "") ?? ""
            let ruleLine = lines.first(where: { $0.contains("," + policy) }) ?? ""
            guard !policy.isEmpty, !kind.isEmpty else { continue }
            let selected = ruleLine.components(separatedBy: " # ").dropFirst().joined(separator: " # ")
            rows.append(["host": hostname, "policy": String(policy.prefix(80)),
                         "rule_type": String(kind.prefix(45)), "selected": String(selected.prefix(90))])
        }
        return ["source": source, "checked_at": Int(Date().timeIntervalSince1970),
                "state": rows.count == hostnames.count ? "verified_rule_matches" : "partial_rule_matches",
                "rules": rows, "scope": "configuration_rule_test_not_live_request_capture"]
    }
}
