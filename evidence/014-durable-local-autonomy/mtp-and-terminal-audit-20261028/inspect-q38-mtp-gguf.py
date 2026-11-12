import struct,json
p='/mnt/data/forge-c/ollama-models/blobs/sha256-2bb22714289826d7b9e0ba376c3ce47d08bce39abe598745857c44d88c09bdbf'
f=open(p,'rb')
def n(fmt): return struct.unpack('<'+fmt,f.read(struct.calcsize('<'+fmt)))[0]
def s(): return f.read(n('Q')).decode()
def val(t,keep=False):
 if t==8:
  z=n('Q'); b=f.read(z) if keep else f.seek(z,1); return b.decode() if keep else None
 if t==9:
  a=n('I');count=n('Q')
  for _ in range(count): val(a)
  return {'array_type':a,'count':count} if keep else None
 fmt={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}[t]
 return n(fmt)
magic=f.read(4);v=n('I');nt=n('Q');nk=n('Q');meta={}
for _ in range(nk):
 k=s();t=n('I');keep='mtp' in k or k in ['general.architecture','general.name','general.file_type']
 x=val(t,keep)
 if keep:meta[k]=x
names=[]
for _ in range(nt):
 name=s();dims=n('I');f.seek(8*dims+4+8,1)
 if 'mtp' in name or 'nextn' in name:names.append(name)
print(json.dumps({'magic':magic.decode(),'version':v,'tensor_count':nt,'metadata':meta,'mtp_tensor_names':names,'header_bytes':f.tell()}))
