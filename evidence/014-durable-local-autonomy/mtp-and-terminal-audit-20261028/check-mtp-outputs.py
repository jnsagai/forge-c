import json,subprocess
from pathlib import Path
Q=Path('/mnt/data/forge-c/production-local-014/deployment/mtp-q38-20261028')
checks={}
for mode in ['baseline','mtp']:
 for name in ['crc8','popcount']:
  for repeat in range(2):
   source=Q/(mode+'-'+name+'-'+str(repeat)+'.c')
   body=source.read_text().split('\nint main(void)')[0]
   if name=='crc8':
    oracle=r'''
static unsigned char ref_crc(const unsigned char *p,unsigned long n){
 unsigned int r=0; for(unsigned long k=0;k<n;k++){r^=(unsigned int)p[k]<<8;
 for(int j=0;j<8;j++)r=(r<<1)^((r&0x8000)?0x10700:0);r&=0xff00;} return (unsigned char)(r>>8);
}
int main(void){
 unsigned char d[512]; unsigned int s=0x12345678;
 for(unsigned int x=0;x<65536;x++){d[0]=(unsigned char)x;d[1]=(unsigned char)(x>>8);
 if(crc8(d,2)!=ref_crc(d,2))return 1;}
 for(unsigned int x=0;x<256;x++){d[0]=(unsigned char)x;if(crc8(d,1)!=ref_crc(d,1))return 2;}
 for(unsigned int i=0;i<1000;i++){unsigned int n=i%513;
 for(unsigned int j=0;j<n;j++){s=s*1664525u+1013904223u;d[j]=(unsigned char)(s>>24);}
 if(crc8(d,n)!=ref_crc(d,n))return 3;}return 0;
}
'''
    count=66792
   else:
    oracle=r'''
int main(void){unsigned int s=0x12345678;
 for(unsigned int i=0;i<100000;i++){s=s*1664525u+1013904223u;if(popcount32(s)!=(unsigned int)__builtin_popcount(s))return 1;}
 if(popcount32(0)!=0 || popcount32(0xffffffffu)!=32)return 2; return 0;
}
'''
    count=100002
   test=source.with_name(source.stem+'-extended.c');test.write_text(body+oracle);exe=test.with_suffix('.test')
   compiled=subprocess.run(['/mnt/data/forge-c/toolchains/LLVM-19.1.7-Linux-X64/bin/clang','-std=c11','-O2','-Wall','-Wextra','-Werror',str(test),'-o',str(exe)],capture_output=True,text=True,timeout=15)
   rec={'compiled':compiled.returncode==0,'compiler_error':compiled.stderr,'comparison_count':count}
   if compiled.returncode==0:rec['test_exit']=subprocess.run([str(exe)],timeout=10).returncode
   checks[source.stem]=rec
result={'scope':'Independent bounded functional fixtures, no inference; not driver/product qualification','checks':checks}
(Q/'extended-checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
