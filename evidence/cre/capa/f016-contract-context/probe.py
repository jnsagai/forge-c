import json,tempfile
from pathlib import Path
from forge_factory.assurance import register_contract as RC
with tempfile.TemporaryDirectory() as td:
 w=Path(td)
 files={
  '.forge-run/manifest.json':json.dumps({'delivery':{'build':{}},'delivered':[{'path':'software/hal/stm32n6xx_hal_spi.h','role':'delivered_code'}]}),
  'software/hal/stm32n6xx_hal_spi.h':'#ifndef SPI_H\n#define SPI_H\ntypedef struct { DMA_HandleTypeDef *hdma; } SPI_HandleTypeDef;\nint HAL_SPI_Init(SPI_HandleTypeDef *h);\n#endif\n',
  'inputs/vendor/include/stm32n6xx_hal.h':'typedef int DMA_HandleTypeDef;\n#include "stm32n6xx_hal_spi.h"\n',
  RC.EFFECTS:json.dumps({'effects':[{'case':'NULL_INIT','swr':'SWR-001','op':'no_write'}]}),
  RC.CALLS:json.dumps({'calls':{'NULL_INIT':{'function':'HAL_SPI_Init','args':['NULL']}}}),
 }
 for rel,body in files.items():
  p=w/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body)
 errors=RC.check_compiles(w,[w/'software/hal'],'stm32n6xx_hal_spi.h')
 if errors:
  assert any('DMA_HandleTypeDef' in e for e in errors),errors
  print('SYMPTOM_PRESENT:contract probe omits configured HAL dependency types')
  raise SystemExit(1)
 (w/RC.CALLS).write_text(json.dumps({'calls':{'NULL_INIT':{'function':'HAL_SPI_Init','args':['NULL','0U']}}}))
 assert RC.check_compiles(w,[w/'software/hal'],'stm32n6xx_hal_spi.h'), 'bad call was silently accepted'
 print('SYMPTOM_ABSENT')
