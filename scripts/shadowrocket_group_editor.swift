import AppKit
import ApplicationServices
import Foundation

// Dedicated, fail-closed GUI adapter for the Shadowrocket macOS group editor.
// No private DB writes, no global route changes, no VPN disconnects.
enum EditorError: Error { case permission, absent, focusLost, unexpectedUI, invalidRegex, failedPaste }

func pause(_ time: Double = 0.12) { Thread.sleep(forTimeInterval: time) }
func click(_ pt: CGPoint) {
    for typ in [CGEventType.mouseMoved, .leftMouseDown, .leftMouseUp] {
        CGEvent(mouseEventSource: nil, mouseType: typ, mouseCursorPosition: pt, mouseButton: .left)?
            .post(tap: .cghidEventTap)
        pause()
    }
}
func chord(_ key: CGKeyCode) {
    for isDown in [true, false] {
        if let e = CGEvent(keyboardEventSource: nil, virtualKey: key, keyDown: isDown) {
            e.flags = .maskCommand
            e.post(tap: .cghidEventTap)
        }
        pause(0.08)
    }
}
func applicationIsFront() -> Bool {
    NSWorkspace.shared.frontmostApplication?.bundleIdentifier == "com.liguangming.Shadowrocket"
}
func findWindow(_ pid: pid_t) throws -> CGRect {
    let arr = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String:Any]] ?? []
    let entries = arr.filter { ($0[kCGWindowOwnerPID as String] as? Int32) == pid }
    let frames = entries.compactMap { info -> CGRect? in
        guard let d = info[kCGWindowBounds as String] as? [String: Any],
          let x = d["X"] as? CGFloat, let y = d["Y"] as? CGFloat,
          let w = d["Width"] as? CGFloat, let h = d["Height"] as? CGFloat else { return nil }
        return CGRect(x:x,y:y,width:w,height:h)
    }
    guard let b = frames.max(by:{$0.width*$0.height < $1.width*$1.height}),
      b.width > 650, b.width < 1050, b.height > 720, b.height < 1100
    else { throw EditorError.unexpectedUI }
    return b
}
func focusGuard() throws {
    guard applicationIsFront() else { throw EditorError.focusLost }
}
func cloneClipboard(_ board: NSPasteboard) -> [NSPasteboardItem] {
    // NSPasteboardItem does not implement NSCopying on macOS 26.
    // Recreate supported type/data pairs in memory (never persist clipboard).
    return (board.pasteboardItems ?? []).map { source in
        let item = NSPasteboardItem()
        for type in source.types {
            if let data = source.data(forType:type) {
                item.setData(data, forType:type)
            }
        }
        return item
    }
}
func activateTarget(_ app: NSRunningApplication) throws {
    for _ in 0..<3 {
        _ = app.activate()
        pause(0.45)
        if applicationIsFront() { return }
    }
    throw EditorError.focusLost
}
func valid(_ original: String) -> Bool {
    let s=original.uppercased()
    return s.count < 220 && s.hasPrefix("(?I)") && s.contains("JAPAN 14")
}
func copyInput() throws -> String {
    try focusGuard()
    chord(0) // command A
    chord(8) // command C
    pause(0.18)
    return NSPasteboard.general.string(forType:.string) ?? ""
}
func focusRegex(_ w: CGRect) throws -> String {
    try focusGuard()
    // First verify the modal is for the only group we are allowed to edit.
    click(CGPoint(x:w.minX+315,y:w.minY+270))
    pause(0.17)
    guard try copyInput().trimmingCharacters(in:.whitespacesAndNewlines) == "OpenAI-Resilience"
    else {throw EditorError.unexpectedUI}
    try focusGuard()
    click(CGPoint(x:w.minX+315,y:w.minY+552))
    pause(0.2)
    return try copyInput()
}
func clickInfo(_ w: CGRect) throws {
    try focusGuard()
    click(CGPoint(x:w.minX+w.width-36,y:w.minY+166))
    pause(0.35)
}
func openEditor(_ w: CGRect) throws -> String {
    // First try the already-open edit sheet; if it is not available,
    // navigate to the last-used Proxy Group list via the sidebar.
    var text = try focusRegex(w)
    if valid(text) { return text }
    try focusGuard()
    click(CGPoint(x:w.minX+63,y:w.minY+97)) // Configuration sidebar
    pause(0.35)
    try clickInfo(w)
    text = try focusRegex(w)
    if valid(text) { return text }
    throw EditorError.unexpectedUI
}
func apply(_ requested: String, expected: String) throws {
    let allowed = [
       "(?i)(JAPAN 04|JAPAN 14|SEATTLE 05|SAN JOSE 07)",
       "(?i)(JAPAN 04|JAPAN 14|SAN JOSE 07)",
       "(?i)(JAPAN 04|JAPAN 14)",
       "(?i)(JAPAN 14)"
    ]
    guard allowed.contains(requested), allowed.contains(expected)
    else {throw EditorError.invalidRegex}
    guard AXIsProcessTrusted(), CGPreflightPostEventAccess() else {throw EditorError.permission}
    guard let app=NSRunningApplication.runningApplications(withBundleIdentifier:"com.liguangming.Shadowrocket").first
    else {throw EditorError.absent}
    let prev=NSWorkspace.shared.frontmostApplication
    let pb=NSPasteboard.general
    let backup=cloneClipboard(pb)
    defer {
        pb.clearContents()
        if !backup.isEmpty { _ = pb.writeObjects(backup) }
        if let prev=prev,prev.bundleIdentifier != "com.liguangming.Shadowrocket" {
           prev.activate()
        }
    }
    for _ in 0..<5 {
        app.activate()
        pause(0.16)
        if applicationIsFront() { break }
    }
    try focusGuard()
    let w=try findWindow(app.processIdentifier)
    let original=try openEditor(w)
    guard valid(original) else {throw EditorError.invalidRegex}
    func normalize(_ s: String) -> String {
        s.replacingOccurrences(of:" ",with:"").uppercased()
    }
    // Do not overwrite a manually changed regex, unrecognized profile,
    // or a different automated phase.
    guard normalize(original) == normalize(expected)
    else {throw EditorError.unexpectedUI}
    // One named group only. Clipboard proof checks the field has a group REGEX,
    // not the group NAME nor another text field.
    pb.clearContents()
    pb.setString(requested,forType:.string)
    try focusGuard()
    chord(9) // cmd V
    pause(0.2)
    let verified=try copyInput()
    guard verified == requested else {throw EditorError.failedPaste}
    // The Save button is on the edit sheet, not the parent config.
    try focusGuard()
    click(CGPoint(x:w.minX+570,y:w.minY+195))
    pause(0.65)
    // A click success is NOT proof that Shadowrocket saved anything.
    // Reopen the same group, verify the persisted regex, then close without changes.
    try focusGuard()
    try clickInfo(w)
    let saved = try focusRegex(w)
    guard normalize(saved) == normalize(requested) else { throw EditorError.failedPaste }
    try focusGuard()
    click(CGPoint(x:w.minX+140,y:w.minY+195))
    pause(0.15)
    print("SAVED_AND_REOPEN_VERIFIED group=OpenAI-Resilience phase=\(allowed.firstIndex(of:requested) ?? -1)")
}
func probe() throws {
    guard AXIsProcessTrusted(), CGPreflightPostEventAccess() else {throw EditorError.permission}
    guard let app=NSRunningApplication.runningApplications(withBundleIdentifier:"com.liguangming.Shadowrocket").first
    else {throw EditorError.absent}
    let previous=NSWorkspace.shared.frontmostApplication
    let pb=NSPasteboard.general
    let backup=cloneClipboard(pb)
    defer {
        pb.clearContents()
        if !backup.isEmpty { _ = pb.writeObjects(backup) }
        if let a=previous,a.bundleIdentifier != "com.liguangming.Shadowrocket" {a.activate()}
    }
    try activateTarget(app)
    try focusGuard()
    let win=try findWindow(app.processIdentifier)
    let text=try openEditor(win)
    guard valid(text) else {throw EditorError.invalidRegex}
    click(CGPoint(x:win.minX+140,y:win.minY+195))
    print("READY group=OpenAI-Resilience regex_valid=true")
}
let args=CommandLine.arguments
if args.count == 2 && args[1] == "--check-permissions" {
    let ax=AXIsProcessTrusted()
    let post=CGPreflightPostEventAccess()
    print("ACCESSIBILITY=\(ax ? "granted" : "required") EVENT_CONTROL=\(post ? "granted" : "required")")
    exit(ax && post ? 0 : 77)
}
if args.count == 2 && args[1] == "--probe" {
    do {try probe();exit(0)}
    catch {print("NOT_READY \(String(describing:error))");exit(77)}
}
guard args.count==5,args[1]=="--set",args[3]=="--expect" else {
    print("usage: TunnelSentinelRouteController --set <allowlisted-regex> --expect <previous-regex>")
    exit(2)
}
do {try apply(args[2],expected:args[4]);exit(0)}
catch {
    // No raw clipboard, private URL or regex in diagnostics.
    print("ABORT route-control error=\(String(describing:error))")
    exit(77)
}
