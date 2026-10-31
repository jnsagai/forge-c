#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <limits.h>
#include "candidate.c"
static unsigned checks=0U, failures=0U;
static void verify(int value) { ++checks; if (!value) ++failures; }
struct sequence { unsigned reads; unsigned match_at; uint32_t mask; uint32_t expected; };
static uint32_t read_word(void *arg) {
 struct sequence *s=(struct sequence *)arg;
 unsigned n=s->reads++;
 return n==s->match_at ? s->expected : (s->expected ^ s->mask);
}
static unsigned null_reads=0U;
static uint32_t read_null(void *arg) { verify(arg==NULL); ++null_reads; return 0U; }
int main(void) {
 const uint32_t values[]={0U,UINT32_MAX,0xA55A5AA5U,0x12345678U,0x80000000U};
 for(unsigned lsb=0U;lsb<=34U;++lsb) for(unsigned width=0U;width<=34U;++width)
 for(unsigned v=0U;v<5U;++v) for(unsigned r=0U;r<5U;++r) {
  uint32_t expected=values[v];
  if(width>=1U && width<=32U && lsb<=31U && width<=32U-lsb) {
   uint64_t mask=((UINT64_C(1)<<width)-UINT64_C(1))<<lsb;
   expected=(uint32_t)(((uint64_t)values[v]&~mask)|(((uint64_t)values[r]<<lsb)&mask));
  }
  verify(replace_field(values[v],lsb,width,values[r])==expected);
 }
 const unsigned boundaries[]={0U,31U,32U,33U,UINT_MAX};
 for(unsigned a=0U;a<5U;++a) for(unsigned b=0U;b<5U;++b) {
  unsigned lsb=boundaries[a], width=boundaries[b];
  uint32_t expected=0xA55A5AA5U;
  if(width>=1U && width<=32U && lsb<=31U && width<=32U-lsb) {
   uint64_t mask=((UINT64_C(1)<<width)-UINT64_C(1))<<lsb;
   expected=(uint32_t)(((uint64_t)expected&~mask)|(((uint64_t)0x5AA5A55AU<<lsb)&mask));
  }
  verify(replace_field(0xA55A5AA5U,lsb,width,0x5AA5A55AU)==expected);
 }
 for(unsigned budget=0U;budget<=16U;++budget) for(unsigned at=0U;at<=17U;++at)
 for(unsigned z=0U;z<2U;++z) {
  struct sequence s={0U,at,z ? 0U : 0x00F00000U,0x00500000U};
  int matched=budget>0U && (z || at<budget);
  unsigned reads=matched ? (z ? 1U : at+1U) : budget;
  verify(poll_match(read_word,&s,s.mask,s.expected,budget)==matched);
  verify(s.reads==reads);
 }
 verify(poll_match(NULL,NULL,0U,0U,10U)==-1);
 verify(poll_match(read_null,NULL,UINT32_MAX,0U,2U)==1);
 verify(null_reads==1U);
 printf("checks=%u failures=%u\n",checks,failures);
 return failures ? 1 : 0;
}
