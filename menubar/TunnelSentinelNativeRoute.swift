import AppKit
import ApplicationServices
import Foundation

// Embedded into TunnelSentinel.app: no auxiliary .app or external permissions.


// Restricted Shadowrocket native AX group editor adapter. No browser/private
// database APIs, no clipboard, no global proxy or VPN control.
enum EditorError: Error {
    case accessDenied, appNotRunning, editorNotOpen, ambiguousUI,
         unexpectedRule, readOnlyRule, writeFailed, saveFailed
}
let originalCandidates = ["JAPAN 04", "JAPAN 14", "SEATTLE 05", "SAN JOSE 07"]
// Every allowed filter is a non-empty subset of FOUR known node names,
// always in the canonical order. No arbitrary user-supplied regex can be sent.
let allowedRules:[String] = (1..<16).map { mask in
    "(?i)(" + originalCandidates.enumerated().filter {
        mask & (1 << $0.offset) != 0
    }.map {$0.element}.joined(separator:"|") + ")"
}
func normalized(_ s:String)->String {
    s.uppercased().replacingOccurrences(of:" ",with:"")
}
func attribute(_ e:AXUIElement,_ key:String)->CFTypeRef? {
    var v:CFTypeRef?
    return AXUIElementCopyAttributeValue(e,key as CFString,&v) == .success ? v:nil
}
func getString(_ e:AXUIElement,_ key:String)->String {
    (attribute(e,key) as? String) ?? ""
}
func children(_ e:AXUIElement)->[AXUIElement] {
    (attribute(e,kAXChildrenAttribute) as? [AXUIElement]) ?? []
}
func scan(_ root:AXUIElement, depth:Int=0) -> [AXUIElement] {
    guard depth<14 else {return []}
    AXUIElementSetMessagingTimeout(root,0.6)
    var result=[root]
    for c in children(root).prefix(70) {
        result += scan(c,depth:depth+1)
        if result.count>450 {break}
    }
    return result
}
func appElement()->AXUIElement? {
    guard let app=NSRunningApplication.runningApplications(
        withBundleIdentifier:"com.liguangming.Shadowrocket").first else {return nil}
    let element=AXUIElementCreateApplication(app.processIdentifier)
    AXUIElementSetMessagingTimeout(element,0.6)
    return element
}
struct GroupEditor {
    let sheet:AXUIElement
    let field:AXUIElement
    let save:AXUIElement
    let original:String
}
func findEditor()->GroupEditor? {
    guard let app=appElement(),
      let windows=attribute(app,kAXWindowsAttribute) as? [AXUIElement]
    else {return nil}
    for w in windows.prefix(2) {
        for s in scan(w).filter({getString($0,kAXRoleAttribute)=="AXSheet"}) {
            let elements=scan(s)
            let headings=elements.filter{getString($0,kAXRoleAttribute)=="AXHeading"}
                .map{[getString($0,kAXValueAttribute),getString($0,kAXTitleAttribute),getString($0,kAXDescriptionAttribute)].joined(separator:" ")}
            guard headings.contains(where:{$0.contains("代理分组")}),
                  headings.contains(where:{$0.contains("正则")}),
                  headings.contains(where:{$0.contains("策略")}) else {continue}
            // Use a separate variable to avoid comparing the field to the predicate's
            // closure item accidentally.
            let matchingFields=elements.filter { element in
                guard getString(element,kAXRoleAttribute)=="AXTextField" else {return false}
                let value=getString(element,kAXValueAttribute)
                return allowedRules.contains { normalized($0)==normalized(value) }
            }
            let saveButtons=elements.filter { element in
                guard getString(element,kAXRoleAttribute)=="AXButton" else {return false}
                let label=[getString(element,kAXTitleAttribute),
                             getString(element,kAXValueAttribute),
                             getString(element,kAXDescriptionAttribute)].joined(separator:" ")
                return label.contains("保存")
            }
            guard matchingFields.count==1,saveButtons.count==1 else {return nil}
            return GroupEditor(sheet:s,field:matchingFields[0],save:saveButtons[0],
                               original:getString(matchingFields[0],kAXValueAttribute))
        }
    }
    return nil
}
func groupListControls() -> (AXUIElement,AXUIElement,String)? {
    guard let app=appElement(),
          let windows=attribute(app,kAXWindowsAttribute) as? [AXUIElement] else {return nil}
    var matches:[(AXUIElement,AXUIElement,String)]=[]
    for w in windows.prefix(2) {
        let items=scan(w)
        for row in items where getString(row,kAXRoleAttribute)=="AXButton" {
            let summary=[getString(row,kAXValueAttribute),
                         getString(row,kAXTitleAttribute),
                         getString(row,kAXDescriptionAttribute)].joined(separator:" ")
            guard summary.contains("OpenAI-Resilience") &&
                  summary.contains("FALLBACK") else {continue}
            var parentRef:CFTypeRef?
            guard AXUIElementCopyAttributeValue(row,kAXParentAttribute as CFString,
                                                 &parentRef) == .success,
                  let raw=parentRef,CFGetTypeID(raw)==AXUIElementGetTypeID()
            else {continue}
            let others=children(raw as! AXUIElement).filter {
                getString($0,kAXRoleAttribute)=="AXButton"
            }
            guard others.count==2 else {continue}
            let other=others.first(where:{
                !([getString($0,kAXValueAttribute),
                   getString($0,kAXTitleAttribute),
                   getString($0,kAXDescriptionAttribute)].joined(separator:" ")).contains("OpenAI-Resilience")
            })
            if let info=other {matches.append((row,info,summary))}
        }
    }
    return matches.count==1 ? matches[0] : nil
}
func ensureEditor() -> GroupEditor? {
    if let editor=findEditor() { return editor }
    guard let (_,info,_) = groupListControls() else {return nil}
    let rc=AXUIElementPerformAction(info,kAXPressAction as CFString)
    guard rc == .success else {return nil}
    Thread.sleep(forTimeInterval:0.6)
    let ed=findEditor()
    return ed
}
func cancelEditor(_ ed:GroupEditor) {
    let buttons=scan(ed.sheet).filter {
        getString($0,kAXRoleAttribute)=="AXButton"
    }
    // Close glyph is the only action-enabled button in the sheet heading
    // other than the named Save button.
    let close=buttons.first { button in
        let label=[getString(button,kAXValueAttribute),
                   getString(button,kAXTitleAttribute),
                   getString(button,kAXDescriptionAttribute)].joined(separator:" ")
        return !label.contains("保存")
    }
    if let button=close {
        _=AXUIElementPerformAction(button,kAXPressAction as CFString)
    }
}
func currentBackend()->Int32 {
    guard AXIsProcessTrusted() else {print("CURRENT_UNKNOWN accessibility");return 77}
    guard let (_,_,label)=groupListControls() else {
        print("CURRENT_UNKNOWN group_list_not_visible")
        return 77
    }
    // Value is a real native fallback-group UI label, not public IP geolocation.
    guard let r=label.range(of:"FALLBACK >") else {return 77}
    let value=label[r.upperBound...].trimmingCharacters(in:.whitespacesAndNewlines)
    guard !value.isEmpty, value.count <= 90 else {return 77}
    print("CURRENT_GROUP_NODE "+value)
    return 0
}
func requestAccessibilityConsent()->Int32 {
    // macOS alone owns this prompt and approval. Never mutate its TCC database.
    let result=AXIsProcessTrustedWithOptions(
        ["AXTrustedCheckOptionPrompt":true] as CFDictionary)
    print(result ? "ACCESSIBILITY_ALREADY_GRANTED" : "ACCESSIBILITY_SYSTEM_APPROVAL_REQUIRED")
    return result ? 0:77
}

func reportLaunchServicesPermissions()->Int32 {
    let ax=AXIsProcessTrusted()
    let post=CGPreflightPostEventAccess()
    let report:[String:Any]=[
        "source":"signed_macos_launchservices_app",
        "timestamp":Int(Date().timeIntervalSince1970),
        "accessibility":ax ? "granted":"required",
        "event_control":post ? "granted":"required"
    ]
    let folder=FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Application Support/OpenAILinkGuardian",isDirectory:true)
    let output=folder.appendingPathComponent("routecontroller_launchservices_auth.json")
    if let data=try? JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys]) {
        try? data.write(to:output,options:[.atomic])
    }
    return ax && post ? 0:77
}
func capabilities()->Int32 {
    let granted=AXIsProcessTrusted(), events=CGPreflightPostEventAccess()
    print("ACCESSIBILITY=\(granted ? "granted" : "required") EVENT_CONTROL=\(events ? "granted" : "required")")
    return granted && events ? 0 : 77
}
func probe()->Int32 {
    guard AXIsProcessTrusted() else {print("NOT_READY accessibility");return 77}
    guard appElement() != nil else {print("NOT_READY app");return 77}
    guard let ed=ensureEditor() else {print("NOT_READY editor_not_found");return 77}
    var settable:DarwinBoolean=false
    let result=AXUIElementIsAttributeSettable(ed.field,kAXValueAttribute as CFString,&settable)
    var actions:CFArray?
    let aresult=AXUIElementCopyActionNames(ed.save,&actions)
    let canPress=(actions as? [String] ?? []).contains("AXPress")
    guard result == .success && settable.boolValue && aresult == .success && canPress
    else {print("NOT_READY edit_capabilities");return 77}
    let index=allowedRules.firstIndex(where:{normalized($0)==normalized(ed.original)}) ?? -1
    cancelEditor(ed)
    Thread.sleep(forTimeInterval:0.4)
    print("READY group_editor=verified expected_rule_phase=\(index) writable=true save_action=true")
    return 0
}
func update(to requested:String,expected:String)->Int32 {
    guard allowedRules.contains(where:{normalized($0)==normalized(requested)}) &&
          allowedRules.contains(where:{normalized($0)==normalized(expected)})
    else {print("ABORT invalid_phase");return 77}
    guard AXIsProcessTrusted() else {print("ABORT accessibility");return 77}
    guard let ed=ensureEditor() else {print("ABORT editor_not_found");return 77}
    guard normalized(ed.original)==normalized(expected)
    else {print("ABORT existing_policy_mismatch");return 77}
    var settable:DarwinBoolean=false
    guard AXUIElementIsAttributeSettable(ed.field,kAXValueAttribute as CFString,&settable) == .success,
          settable.boolValue else {print("ABORT read_only_rule");return 77}
    guard AXUIElementSetAttributeValue(ed.field,kAXValueAttribute as CFString,
                                        requested as CFString) == .success,
          normalized(getString(ed.field,kAXValueAttribute))==normalized(requested)
    else {
        _ = AXUIElementSetAttributeValue(ed.field,kAXValueAttribute as CFString,ed.original as CFString)
        print("ABORT failed_to_change_field");return 77
    }
    guard AXUIElementPerformAction(ed.save,kAXPressAction as CFString) == .success
    else {
        _ = AXUIElementSetAttributeValue(ed.field,kAXValueAttribute as CFString,ed.original as CFString)
        print("ABORT save_action_failed");return 77
    }
    Thread.sleep(forTimeInterval:0.3)
    // Reopen the same protected group and verify the persisted regex.
    // Successful AXPress alone is NEVER evidence the route was saved.
    guard findEditor()==nil else {
        print("ABORT edit_dialog_remained_open")
        return 77
    }
    var reopened:GroupEditor?=nil
    for _ in 0..<10 {
        if let editor=ensureEditor() {
            reopened=editor
            break
        }
        Thread.sleep(forTimeInterval:0.25)
    }
    guard let verified=reopened,
          normalized(verified.original)==normalized(requested)
    else {
        print("ABORT saved_policy_unverified")
        return 77
    }
    cancelEditor(verified)
    // Real *business* recovery still requires the next observed Codex stream.
    print("POLICY_PERSISTED group=OpenAI-Resilience pending_native_backend_verification=true")
    return 0
}


// Safe native API used in-process by the TunnelSentinel menubar application.
enum IntegratedGroupController {
    static func currentNode() -> String? {
        guard AXIsProcessTrusted(), let (_,_,label)=groupListControls(),
              let index=label.range(of:"FALLBACK >") else {return nil}
        let value=label[index.upperBound...].trimmingCharacters(in:.whitespacesAndNewlines).uppercased()
        let possible=originalCandidates.filter {value.hasSuffix($0)}
        return possible.count==1 ? possible[0] : nil
    }
    static func readRule() -> String? {
        guard AXIsProcessTrusted(),let editor=ensureEditor() else{return nil}
        let rule=editor.original
        cancelEditor(editor)
        return rule
    }
    static func apply(_ target:String, expecting previous:String) -> Bool {
        // Only exact known, nonempty canonical subsets may be written.
        guard AXIsProcessTrusted(),
              allowedRules.contains(where:{normalized($0)==normalized(target)}),
              allowedRules.contains(where:{normalized($0)==normalized(previous)})
        else{return false}
        // Uses the verified AXValue + AXPress + reopen/readback logic already
        // tested with a no-change save on the original four-node policy.
        return update(to:target,expected:previous)==0
    }
}
