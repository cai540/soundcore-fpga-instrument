"""Fail closed on timing/resources, including red/classed negative slack cells."""
from pathlib import Path
import argparse,hashlib,json,re,shutil
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/organic_20261027'
def timing(html):
    violations={title:int(re.search(re.escape(title)+r'</td>\s*<td[^>]*>(\d+)</td>',html)[1])
        for title in ['Numbers of Setup Violated Endpoints','Numbers of Hold Violated Endpoints']}
    result={'violations':violations}
    for key,anchor in [('setup_slack_ns','Setup_Slack_Table'),('hold_slack_ns','Hold_Slack_Table')]:
        start=html.index('name="'+anchor+'"');section=html[start:html.index('</table>',start)]
        result[key]=float(re.search(r'<tr[^>]*>\s*<td[^>]*>1</td>\s*<td[^>]*>([-\d.]+)</td>',section)[1])
    return result
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',default='build/organic_20261027')
    parser.add_argument('--firmware',default='build/soundcore_organic_timbres_20261027.fs')
    parser.add_argument('--log',default='gowin_pipeline.log')
    args=parser.parse_args();OUT=ROOT/args.out
    old=timing((ROOT/'build/organic_20261027/failed_two_stage_timing/pressure_i2s_panel_oled_ble_experiment_60k_tr_content.html').read_text())
    assert old['setup_slack_ns']==-21.046 and old['violations']['Numbers of Setup Violated Endpoints']==1243
    result=timing((ROOT/'board/impl/pnr/pressure_i2s_panel_oled_ble_experiment_60k_tr_content.html').read_text())
    rpt=(ROOT/'board/impl/pnr/pressure_i2s_panel_oled_ble_experiment_60k.rpt.txt').read_text();resources={}
    for key in ['Logic','BSRAM','DSP']:
        m=re.search(r'^\s*'+key+r'\s*\|\s*([\d.]+)/([\d.]+)',rpt,re.M)
        resources[key]={'used':float(m[1]),'total':int(m[2])}
    result['resources']=resources
    print(json.dumps(result,indent=2),flush=True)
    assert not any(result['violations'].values()) and min(result['setup_slack_ns'],result['hold_slack_ns'])>=0
    assert all(x['used']<=x['total'] for x in resources.values())
    assert 'Bitstream generation completed' in (OUT/args.log).read_text()
    for source,name in [('pressure_i2s_panel_oled_ble_experiment_60k_tr_content.html','timing_report.html'),
                        ('pressure_i2s_panel_oled_ble_experiment_60k.rpt.txt','resource_report.txt')]:
        shutil.copy2(ROOT/'board/impl/pnr'/source,OUT/name)
    target=ROOT/args.firmware
    shutil.copy2(ROOT/'board/impl/pnr/pressure_i2s_panel_oled_ble_experiment_60k.fs',target)
    result.update(firmware=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        user_code=re.search(r'//UserCode:\s*(\S+)',target.read_text())[1],programmed=False)
    (OUT/'build_validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
