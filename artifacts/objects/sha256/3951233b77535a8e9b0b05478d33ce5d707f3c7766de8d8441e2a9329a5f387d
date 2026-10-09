import sys, json
sys.path.insert(0, '/workspace')
from office_trace_bench.spreadsheet import original_content
from office_trace_bench.verify import Checks
src = '/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-RETAIL/input/mrtssales92-present.xlsx'
out = '/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-RETAIL/work/roundtrip_test.xlsx'
c = Checks({'dataset_id':'retail','kind':'xlsx'})
original_content(src, out, c)
rep = c.finish()
print(json.dumps({k:v for k,v in rep['checks'].items() if not v['ok']}, indent=1))
print('FAILURES', rep['failures'])
