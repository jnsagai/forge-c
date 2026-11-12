# Actual SWE.4 pass, local transfer and subsequent simulation progress

Current runtime9b4c390, actual native01M63ZTJ5QM1R96484Y2KN97H6.
**INS-SWE.4-001 PASS at15:33:48UTC**, no findings, frozen baseline
92a66ef1e1ab535dd26d217b1611e4972a7f9c1fcfa2780a7b7231554c3a9fa0.
A read-only check confirms current baseline and deterministic gate PASS. All17
phase/report/test/coverage/inspection/tool-log members were copied to local loop10
and each hash/size verified. Transfer archiveSHA
dfdde2f2334a0d031ff85c7f11729ed4c69fa9bc52cda948b698cdd52d2f1292.
The upstream actual SWE.3 diagram-lookup failures remain unresolved.

At15:46:05UTC Renode v1.17.0 reported a test_performance.c compilation failure
(void value used as a value),23checks passed/1failed across two images.
At15:46:25UTC the subsequent actual tool result **PASS,27checks passed,0failed**,
exit0 across two images, Cortex-M55 behavioural CRC model. Prior failure remains
in the append-only tool evidence. This is declared simulation evidence:
silicon_verified=false. No physical WCET, hardware qualification or generic
local-model repair capability follows from this authoring feedback.

At15:47:32UTC the current run is RUNNING in **SWE.5 author**,170provider requests
in this run. SWE.5 inspection, host integration completion and SWE.6 remain pending.
This does not close strict M1 or formal qualification. See live-swe5.json,
verification.json and actual-target-tool-results.json for the actual observations.
The complete final package will still be collected after terminal reconciliation.
