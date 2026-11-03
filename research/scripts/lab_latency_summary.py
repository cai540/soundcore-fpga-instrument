"""Summarize manually measured LAB trials. Empty/invalid rows cannot become passes."""
from pathlib import Path
import argparse,csv,json,collections
import numpy as np

def summarize(rows):
 groups=collections.defaultdict(list);invalid=[]
 for i,row in enumerate(rows,2):
  if not row.get('latency_ms','').strip():continue
  try:
   value=float(row['latency_ms'])
   if not np.isfinite(value) or value<=0:raise ValueError('nonpositive/nonfinite latency')
   if not row.get('source_csv') or not row.get('input_definition') or not row.get('output_definition'):raise ValueError('missing source or threshold definition')
   key=tuple(row.get(k,'')for k in ('firmware','timbre','bank','pad','force','input_definition','output_definition'))
   groups[key].append(value)
  except ValueError as e:invalid.append(dict(line=i,error=str(e)))
 results=[]
 for key,values in groups.items():
  x=np.array(values)
  results.append(dict(zip(('firmware','timbre','bank','pad','force','input_definition','output_definition'),key))|
   dict(trials=len(x),minimum_ms=float(x.min()),median_ms=float(np.median(x)),p95_ms=float(np.percentile(x,95)),
        maximum_ms=float(x.max()),stdev_ms=float(np.std(x)),peak_to_peak_ms=float(np.ptp(x)),
        basic_le10ms=bool(np.all(x<=10)),advanced_le5ms=bool(np.all(x<=5)),strict_lt5ms=bool(np.all(x<5)),
        zero_jitter_claimed=False))
 if not results:raise ValueError('No measured trials were entered; no result can be issued')
 return dict(groups=results,invalid_rows=invalid,all_advanced_within5ms=not invalid and all(r['advanced_le5ms']for r in results),
             deterministic_latency_proven=False,note='Jitter statistics and input sampling phase must be explained; this script cannot prove literal zero jitter')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('csv',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 with a.csv.open(encoding='utf-8-sig',newline='')as f:result=summarize(list(csv.DictReader(f)))
 a.out.mkdir(parents=True,exist_ok=True);(a.out/'latency_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(result,ensure_ascii=False,indent=2))
 if result['invalid_rows']:raise SystemExit('Invalid rows retained; acceptance not issued')
if __name__=='__main__':main()
