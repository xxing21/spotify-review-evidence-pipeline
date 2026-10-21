# Final configuration: comparison with original human labels

All 50 original human labels and earlier evaluation outputs are preserved. This evaluation uses the final batch-twenty enrichment configuration. Human answers are not model inputs, and the later adjudicated reference is not substituted.

| Field | Agreement |
|---|---:|
| topic | 74% |
| intent | 86% |
| severity | 72% |

Severity MAE: 0.320; sentiment MAE: 0.198. There are 24 reviews with a topic, intent or severity difference.

Topic agreement fell from 82% to 74%, intent from 88% to 86%; severity agreement rose from 66% to 72%. These are descriptive small-sample comparisons, not a statistically established change in population accuracy. No labels or prompts were retuned to improve the reported scores.

Coverage remains limited: the original human reference has 32 other, 10 usability, 5 playback, 2 catalog and 1 support case; no access, billing or downloads case. Eight original human cases are marked ambiguous. Literal quote validity and feature-term matches are code-grounded, not semantic accuracy.

Concrete recurring failures: the model still labels the resolved crash/support update as playback/complaint/severity 4 against the original human support/praise/1. Ads with limited functionality are labeled billing rather than human usability. Several general criticisms are severity 2 against human severity 1; the shared rubric and human preferences differ on that boundary. Explicit Premium restrictions are billing under the rubric while a retained human answer is other. These discrepancies are visible rather than silently adjudicated away.

## Complete core disagreement list

| ID and unchanged comment | Original human topic / intent / severity | Final AI topic / intent / severity |
|---|---|---|
| `292ce26a-815d-4bce-a3b6-93cb6c9e7e2c` — Staff must be full of mentally ill kool-aid heads. Banning conservative music that speaks truth. Spotify is doing all they can to protect pedophiles, by banning Christian songs discussing the path the devil leads you down. Pride is a sin. | other / complaint / 2 | catalog / complaint / 3 |
| `991b6b3a-f511-458a-a5b7-234f78048fb5` — Ads were okay, but limited functionality..it's just too much | usability / complaint / 2 | billing / complaint / 3 |
| `0c6ca545-3f89-4da6-b3db-1a352371fb6e` — Hate this application 🤮🤮🤮🤮🤮🤮 | other / complaint / 1 | other / complaint / 2 |
| `1fc8b08f-7d6a-472f-b317-8ceb28d00f22` — Duo Premium .... No ads at all! | usability / praise / 1 | other / praise / 1 |
| `723f07de-9881-4049-8680-1a9e25652914` — Update: I reached out to Spotify Support and with some help from Sarah I was able to get the app working again. Old Post:Normally, the app works great, and I use it constantly. I tried to open it today, and it keeps crashing every time. I've tried uninstalling and reinstalling, and updating. Nothing seems to work unfortunately. | support / praise / 1 | playback / complaint / 4 |
| `47428620-ec21-424d-a515-0b0b0012a5cf` — This app is bad work | other / complaint / 1 | other / complaint / 2 |
| `46842184-32f8-4088-ac15-2a700a7e94ed` — asem, lirik nya kdang gaada kek mana?? | other / unclear / 1 | catalog / complaint / 2 |
| `657f1b77-0183-4b06-bf48-5e6d9ab08f9a` — Hate This application 👎 | other / complaint / 1 | other / complaint / 2 |
| `372d4e67-59cc-4c54-879f-3e8a202ee554` — Please ye ads ko thoda kumm Karo harr ek song ke baad ad 🙏🙄 | usability / complaint / 1 | usability / request / 1 |
| `47f1406d-4918-4d60-9647-5ca8e610caca` — Very poor updates as we cannot playback the songs and most bad updates are happening it is affecting the spotify quality | playback / complaint / 3 | playback / complaint / 4 |
| `f4c8146a-d5c8-4168-b00e-21af666afc6a` — Unconditional love, Stoli Canales | other / unclear / 1 | other / praise / 1 |
| `3ddb3f4e-f7b9-430b-b335-eadc6d321f46` — Deleting this App. The new update suck, we can't choose our fvrt songs after some clicks, we can't CHOOSE song after a song played, and we can't turn off shuffle option. They are pushing us to upgrade to Premium subscription. No wonder if you guys loose ratings and users. Anyway i am deleting this app after years of using. | usability / complaint / 4 | usability / cancellation / 4 |
| `16d640e9-b281-4746-9562-c7dbcf7126b6` — It's my best music app but now it's not...everything basic features is premium.... | other / complaint / 2 | billing / complaint / 3 |
| `46c0b49f-83a1-427e-8f0b-cef62e3c94b5` — Are you out of your mind? This is dangerous! Listening to music in a normal volume and suddenly an add starts and my ears feel like they explode!! Stop this BS, or you're gonna destroy someones ears. | usability / complaint / 3 | playback / complaint / 3 |
| `283b5843-a992-464f-b1dc-9dc7281ff390` — Beth, we all got to give me a free dollar to go with 3 months, bro I can't be like | other / unclear / 1 | billing / unclear / 1 |
| `2aa566c6-b98d-4513-b900-83702a8db8eb` — Nice app, very less advertising | other / praise / 1 | usability / praise / 1 |
| `8c0546b0-ce43-4a36-9d33-9f979e98d522` — 1-Lyrics not getting loaded, 2-can't go back to or start song where to wanted. Pathetic update | playback / complaint / 3 | catalog / complaint / 3 |
| `b58dd6f0-ad88-4319-b6db-58afb60c37c1` — The only thing Spotify lacks is the ability to organize saved <br>albums/artists into collections. Would definitely deserve 5 stars if it <br>included this feature. | usability / complaint / 2 | usability / request / 1 |
| `1a41c7e1-a655-4c63-b4db-c22bdff18003` — Worst application 👎👎👎 | other / complaint / 1 | other / complaint / 2 |
| `dceb14e7-2df0-422f-bb2b-73d7c373159a` — I gave one star because I can't give any less than that. the new update is sooooooo annoying like I can't even play the songs that I like and I can't rewind songs what the heck | usability / complaint / 4 | playback / complaint / 4 |
| `ac4e860a-c042-49cc-90f3-189591c336ac` — paying for subscribing but unable to play in offline mode really? | playback / complaint / 3 | downloads / complaint / 4 |
| `9034d675-9582-49b6-a1c1-c4ddabf8baf1` — Worst app ever too much ad | usability / complaint / 1 | usability / complaint / 2 |
| `d2f3874f-d15d-4a2f-bb97-4f1213defa46` — Too expensive and the free version is pretty much unusable with constant ads... Every two or three songs.. Forget it | usability / complaint / 2 | usability / complaint / 3 |
| `99b93e31-9f15-4daa-88ac-349ab0419c48` — This update very bad for everyone.old Spotify. we all want. | other / complaint / 1 | usability / request / 1 |

Known API charge estimate: US$0.002192025; 3 new calls, no missing usage. Original labels SHA-256: `4800864ae69dfb28d90a1b4f4abe7bc5d040e8e4b8e560103ef28b9ad54c1d86`.
