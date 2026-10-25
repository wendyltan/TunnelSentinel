import AppKit
import ApplicationServices
import Foundation

// Lives in the existing TunnelSentinel.app process. No helper app, no CLI TCC
// attribution, no VPN resets. Guardian still provides read-only health data.
final class IntegratedRecovery {
    static let shared = IntegratedRecovery()
    private let base = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Application Support/OpenAILinkGuardian",isDirectory:true)
    private let worker = DispatchQueue(label:"com.wuwendi.TunnelSentinel.nativeRecovery",qos:.utility)
    private var busy = false
    var summary:String {
        let report=load(base.appendingPathComponent("auto_route_ui_status.json"))
        let current=report["state"] as? String ?? "待检查"
        let info:[String:String]=[
            "authorization_required":"需授权 TunnelSentinel",
            "ready_disabled":"关闭","armed":"待命",
            "limited":"监测中 · 切换受限","clash_observing":"Clash 模拟中",
            "recovered":"分组节点已变 · 业务待验","switching":"切换验证中",
            "verifying":"验证中","blocked":"暂停（需检查）",
            "paused":"暂停","rolled_back":"已回滚"
        ]
        return info[current] ?? current
    }
    private let candidates = ["JAPAN 04","JAPAN 14","SEATTLE 05","SAN JOSE 07"]

    private init() {}

    func start() {
        // The existing menubar app (single app) owns the only AX controller.
        // Run at most once at a time, and never on the AppKit main thread.
        Timer.scheduledTimer(withTimeInterval:45, repeats:true) { [weak self] _ in
            self?.tick()
        }
        tick()
    }

    func tick() {
        worker.async { [weak self] in self?.check() }
    }

    private func load(_ url:URL)->[String:Any] {
        guard let data=try? Data(contentsOf:url),
              let json=try? JSONSerialization.jsonObject(with:data) as? [String:Any]
        else{return [:]}
        return json
    }
    private func save(_ value:[String:Any],to url:URL) {
        guard let data=try? JSONSerialization.data(withJSONObject:value,options:[.prettyPrinted,.sortedKeys]) else{return}
        try? data.write(to:url,options:.atomic)
    }
    private func n(_ value:Any?, _ fallback:Int = 0)->Int {
        (value as? NSNumber)?.intValue ?? fallback
    }
    private func s(_ value:Any?,_ fallback:String="")->String {
        value as? String ?? fallback
    }
    private func enabled(_ config:[String:Any])->Bool {
        return config["codex_auto_failover_enabled"] as? Bool == true
            && config["native_fallback_enabled"] as? Bool == true
            && config["native_fallback_group"] as? String == "OpenAI-Resilience"
            && config["codex_stream_sqlite_monitor_enabled"] as? Bool == true
    }
    private func reported(_ status:String,reason:String,node:String="",armed:Bool=false) {
        save(["mode":"integrated_app","state":status,"reason":reason,
              "node":node,"enabled":armed,"checked_at":Int(Date().timeIntervalSince1970)],
             to:base.appendingPathComponent("auto_route_ui_status.json"))
    }
    private func changeRule(excluding names:[String])->String? {
        let remain=candidates.filter{!names.contains($0)}
        guard remain.count>=2 && names.count<=2 else{return nil}
        return "(?i)("+remain.joined(separator:"|")+")"
    }
    private func check() {
        guard !busy else{return}
        busy=true
        defer{busy=false}
        let cfg=load(base.appendingPathComponent("config.json"))
        let live=load(base.appendingPathComponent("status.json"))
        if live["route_management"] as? String == "clash_observe_only" {
            reported("clash_observing",reason:"Clash 本地 API 只读；故障转移待模拟验收",armed:false)
            return
        }
        let operating=enabled(cfg)
        // While disabled, no macOS Accessibility permission is necessary.
        if !operating {
            reported("ready_disabled",reason:"单应用集成已完成，可从 TunnelSentinel 菜单开启",armed:false)
            return
        }
        guard AXIsProcessTrusted() else {
            reported("authorization_required",reason:"请在 macOS 辅助功能中授权 TunnelSentinel",armed:true)
            return
        }
        let status=load(base.appendingPathComponent("status.json"))
        guard status["route_management"] as? String == "native_fallback",
              status["native_fallback_group"] as? String == "OpenAI-Resilience"
        else {reported("paused",reason:"非预期原生分组",armed:true);return}
        let df=DateFormatter()
        df.locale=Locale(identifier:"en_US_POSIX")
        df.dateFormat="yyyy-MM-dd'T'HH:mm:ssZ"
        guard let updated=df.date(from:s(status["updated_at"])),
              (0...100).contains(Int(Date().timeIntervalSince(updated)))
        else {reported("paused",reason:"守护数据已过期",armed:true);return}
        var state=load(base.appendingPathComponent("auto_route_state.json"))
        let now=Int(Date().timeIntervalSince1970)
        let today=String(ISO8601DateFormatter().string(from:Date()).prefix(10))
        if s(state["day"]) != today {
            state["actions_today"]=0
            state["day"]=today
        }
        let currentState=s(state["status"],"armed")
        let excluded=state["excluded"] as? [String] ?? []
        let original="(?i)("+candidates.joined(separator:"|")+")"
        let activeRule=s(state["rule"],original)
        let healthy=status["healthy"] as? Bool == true
        let stateFile=base.appendingPathComponent("auto_route_state.json")
        func persist(_ state:[String:Any], label:String, reason:String,node:String="") {
            save(state,to:stateFile)
            reported(label,reason:reason,node:node,armed:true)
        }
        if currentState=="policy_updated_awaiting_backend_evidence" {
            if !healthy {
                let changed=n(state["last_transition_at"])
                if (0...300).contains(now-changed)
                    && n(state["rollback_attempted_for"]) != changed {
                    state["rollback_attempted_for"]=changed
                    let previous=s(state["previous_rule"],original)
                    let rollback=IntegratedGroupController.apply(previous,expecting:activeRule)
                    if rollback {
                        state["excluded"]=Array(excluded.dropLast())
                        state["rule"]=previous
                        state["phase"]=max(0,excluded.count-1)
                        state["status"]="rolled_back_after_public_failure"
                        persist(state,label:"rolled_back",reason:"公共入口失效，已恢复旧候选")
                    } else {
                        state["status"]="rollback_blocked"
                        persist(state,label:"blocked",reason:"回滚未通过核实")
                    }
                    return
                }
            }
            let selected=IntegratedGroupController.currentNode()
            if let selected, candidates.contains(selected),
               !excluded.contains(selected), selected != s(state["previous_node"]) {
                state["selected_node"]=selected
                state["last_backend_verified"]=true
                state["status"]="armed"
                persist(state,label:"recovered",reason:"已确认新的组内节点；Codex 稳定性继续观察",node:selected)
                return
            }
            if now-n(state["last_transition_at"])>180 {
                state["status"]="backend_unverified"
                persist(state,label:"blocked",reason:"切换后无法确认新的节点")
            } else {
                reported("verifying",reason:"等待 Shadowrocket 新节点证据",armed:true)
            }
            return
        }
        guard healthy else {reported("paused",reason:"基础链路异常，避免误切",armed:true);return}
        guard currentState=="armed" || currentState=="rolled_back_after_public_failure" else {
            reported("blocked",reason:"此前切换未完成验收，请检查日志",armed:true)
            return
        }
        guard let stream=status["codex_stream_diagnostics"] as? [String:Any],
              stream["state"] as? String == "ok",
              let recent=stream["recent_counts"] as? [String:Any] else {
            reported("paused",reason:"无有效 Codex 流故障数据",armed:true);return
        }
        let last=n(stream["last_at"])
        let scan=n(stream["scan_at"])
        let count=["broken_pipe","websocket_handshake","connection_reset"].reduce(0) {
            $0+n(recent[$1])
        }
        guard (0...90).contains(now-scan),
              (0...210).contains(now-last),last>n(state["last_trigger_at"]),
              count>=3 else {
            // Monitoring readiness and switching readiness are distinct:
            // codex_stream is readable, but the group editor can be invisible
            // when the Shadowrocket configuration page is closed or locked.
            // Fail closed, and never advertise "armed" as a writable route.
            if let observed = IntegratedGroupController.currentNode() {
                reported("armed",reason:"故障监测及原生分组读取正常",node:observed,armed:true)
            } else {
                reported("limited",reason:"故障监测正常；Shadowrocket 分组不可读取，暂无法保证自动切换",armed:true)
            }
            return
        }
        guard now-n(state["last_attempt_at"])>=600,
              n(state["actions_today"])<3,excluded.count<2,
              let current=IntegratedGroupController.currentNode(),
              candidates.contains(current), !excluded.contains(current) else {
            reported("blocked",reason:"冷却、次数限制或组内节点不可读取",armed:true)
            return
        }
        let nextExcluded=excluded+[current]
        guard let requested=changeRule(excluding:nextExcluded) else {
            reported("blocked",reason:"剩余候选不足两项",armed:true);return
        }
        state["last_attempt_at"]=now
        state["last_trigger_at"]=last
        // Persist attempted trigger BEFORE the actual AX write to prevent a
        // second process cycle replaying the same fault after an exception.
        save(state,to:stateFile)
        guard IntegratedGroupController.apply(requested,expecting:activeRule) else {
            state["status"]="controller_unavailable"
            persist(state,label:"blocked",reason:"Shadowrocket 分组保存未核实")
            return
        }
        state["excluded"]=nextExcluded
        state["previous_rule"]=activeRule
        state["rule"]=requested
        state["phase"]=nextExcluded.count
        state["previous_node"]=current
        state["last_transition_at"]=now
        state["last_backend_verified"]=false
        state["actions_today"]=n(state["actions_today"])+1
        state["status"]="policy_updated_awaiting_backend_evidence"
        persist(state,label:"switching",reason:"Codex 流故障触发候选排除，等待实际节点确认",node:current)
    }
}
