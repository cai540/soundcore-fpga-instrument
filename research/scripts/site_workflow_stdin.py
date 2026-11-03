"""Portable stdin bridge; credentials remain in process memory only."""
import subprocess,sys,getpass
script='C:/Users/YOUR_USER/.codex/plugins/cache/openai-curated-remote/sites/1.1.2/scripts/site-workflow.mjs'
data=getpass.getpass('Ready for workflow JSON (hidden): ')+'\n'
p=subprocess.run(['node',script,'--project-id','appgprj_6ae4a50a8b848191a72a7de814815348'],input=data,text=True,capture_output=True)
print(p.stdout);print(p.stderr,file=sys.stderr);sys.exit(p.returncode)
