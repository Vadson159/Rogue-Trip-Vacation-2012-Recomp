# Windows verification evidence

These captures come from local Windows x64 development runs. The debug harness
uses scripted controller input and state transitions to reach scenarios
quickly. Its output establishes coverage for the observed scenarios.

| Disc or scenario | Recorded evidence |
| --- | --- |
| FullRUS, arena coverage | [14 arena and boss scenarios](report_stages_fullrus.json) covering all 12 arenas. Each reported arena sample has an empty overlay-interpreter PC list. [Screenshots](suite1_stages_fullrus/) |
| FullRUS, campaign | [Report](report_campaign_save_ending.json) covering the first victory, memory-card save, load after relaunch, resumed campaign, final boss, ending videos and credits. [Screenshots](suite2_campaign_save_ending/) |
| Rus | [Screenshots](suite3_rus/) of the intro, menu, memory-card screen and XLAX. The run artifacts cover these stages of the suite. |
| Runtime diagnostics | [Runtime logs](logs/) include boot region, overlay-cache inventory and debug configuration. An earlier [freeze summary](diagnostics/freeze-summary.json) preserves frame counters and CPU context for investigation. |

The full Europe campaign and dedicated windowed OpenGL suite are open verification items.
See [the developer guide](../../DEVELOPING.md) to rerun individual suites.
