from pathlib import Path
import importlib.util
import unittest
spec=importlib.util.spec_from_file_location('clash_openai_profile',Path(__file__).resolve().parents[1]/'scripts/clash_openai_profile.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ProfileTests(unittest.TestCase):
 def test_isolated(self):
  src={'proxies':[{'name':'nodeZ'}],'proxy-groups':[{'name':'AI','type':'select','proxies':['Proxies']}],'rules':['MATCH,DIRECT']}
  o=m.patch_config(src,'nodeZ');self.assertEqual(o['proxy-groups'][0]['name'],m.GROUP)
  self.assertEqual(o['proxy-groups'][0]['type'],'select')
  self.assertEqual(o['proxy-groups'][1]['name'],'AI')
  self.assertTrue(all(x.endswith(','+m.GROUP) for x in o['rules'][:-1]))
  self.assertEqual(o['rules'][-1],'MATCH,DIRECT');self.assertEqual(src['rules'],['MATCH,DIRECT'])
 def test_requires_real_initial(self):
  with self.assertRaises(ValueError):m.patch_config({'proxies':[],'proxy-groups':[],'rules':[]},'missing')
if __name__=='__main__':unittest.main()
