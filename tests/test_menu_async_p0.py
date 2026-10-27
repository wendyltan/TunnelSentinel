from pathlib import Path
import unittest
s=(Path(__file__).resolve().parents[1]/'menubar'/'TunnelSentinelMenu.swift').read_text()
class MenuP0(unittest.TestCase):
 def test_poll_off_main(self):
  p=s.split('private func pollGuardianServiceIfNeeded()',1)[1].split('private func refreshStatus()',1)[0]
  self.assertIn('DispatchQueue.global(qos: .utility).async',p)
  self.assertIn('15',p)
  r=s.split('private func refreshStatus()',1)[1].split('private func refreshNode()',1)[0]
  self.assertIn('pollGuardianServiceIfNeeded()',r)
  self.assertNotIn('guardianPaused = isPaused()',r)
  self.assertNotIn('guardianRunning = isRunning()',r)
 def test_business_axes_and_timeline_are_distinct(self):
  self.assertIn('dashboardHealthTile("chatgpt"',s)
  self.assertIn('dashboardHealthTile("codex"',s)
  self.assertIn('dashboardHealthTile("computer_use"',s)
  self.assertIn('timelineEventCard(event, in: doc',s)
  self.assertIn('连接恢复不等于模型任务已完成',s)
if __name__=='__main__':unittest.main()
