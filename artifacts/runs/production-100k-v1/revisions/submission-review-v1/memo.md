# Spotify product decision — 100k sample

Priority: **ISSUE-USABILITY**

Prioritize usability for investigation because its aggregate priority score leads the alternatives, supported by reports of accidental loss of favorited songs and difficulty controlling a feature. Playback is a strong alternative: it has higher mean severity and reports describe historical playback disruption and device instability. The cited crash report was later updated to say the problem was fixed, so it supports historical experience rather than an unresolved defect. Billing merits attention for reports of unexpected charges and ads despite a paid subscription; access is another serious concern where users describe losing account access and saved content. These are prioritization signals from complaints, not verified product-wide rates or proof that any issue caused account loss or cancellation.

Alternatives: ISSUE-PLAYBACK, ISSUE-BILLING, ISSUE-ACCESS

## Supporting calculations

- [ISSUE-USABILITY-complaint_count] ISSUE-USABILITY complaint_count: 12575
- [ISSUE-USABILITY-mean_severity] ISSUE-USABILITY mean_severity: 2.594433
- [ISSUE-USABILITY-priority_score] ISSUE-USABILITY priority_score: 32625
- [ISSUE-PLAYBACK-mean_severity] ISSUE-PLAYBACK mean_severity: 3.269779
- [ISSUE-PLAYBACK-priority_score] ISSUE-PLAYBACK priority_score: 23392
- [ISSUE-BILLING-mean_severity] ISSUE-BILLING mean_severity: 2.811751
- [ISSUE-BILLING-priority_score] ISSUE-BILLING priority_score: 17132
- [ISSUE-ACCESS-mean_severity] ISSUE-ACCESS mean_severity: 3.836474
- [ISSUE-ACCESS-priority_score] ISSUE-ACCESS priority_score: 5701

## Source evidence

- ISSUE-USABILITY / `740b1fa0-c1d8-4d0c-b6a9-60e35d737032`: "The interface of the app on PS5 made me lose several of my favorited songs because it makes the remove from favorite too easily to accidentally happen. I'm trying to look through my list and I accidentally hit the wrong button that's not clearly not marked and my favorited song is gone no way to see what was even deleted."
- ISSUE-USABILITY / `00294af3-eddf-4210-8178-071083967479`: "Waking me up at 12:00 at night no way to switch off the feature"
- ISSUE-PLAYBACK / `4a49d8ba-bb87-4abd-b508-38f34dfbcb84`: "**Update: Everything is back to its brilliant best. Thank you** Usually brilliant but a recent update has caused issues. My downloaded music keeps deleting &, more importantly, whenever the app is playing music in the background it's causing stability issues in my phone & causing it to restart, constantly, it's very irritating. I spent ages thinking it was my phone but through a process of elimination, I've tracked the problem to Spotify. Please fix"
- ISSUE-BILLING / `000c2b9a-d116-45dc-b8a8-7b3818d6e834`: "My favourite application for music hands down However, they charged me double ( took me off student plan) without notifying me, plus I'm still a studend"
- ISSUE-BILLING / `002aac37-eaec-476e-a7d7-5aff5738b2fa`: "It's a paid subscription why am i still getting ads. Why is the most popular music streaming app so terrible. It constantly tells me when people on the same network are listening to something, Which I don't care about and is an invasion of their privacy"
- ISSUE-ACCESS / `3c30d5fc-5063-44b6-a6f2-02bbcd8d66f5`: "Yo I'm pissed, been using spotify for a good 2years never had an issue until now when 2days ago I was completely logged out saying my passwords didn't work, when I reset password my whole account was reset to zero , I had premium , all songs saved ..gone for absolutely no reason , my premium account no longer existent.... explain yourselves...I'd like a recompensation for this BS! Oh and that's not all I'm also blocked from getting another premium account ... recompensate and get my premium back"

## Limitations

This recommendation covers the selected review sample and historical experiences. Current relevance requires validation. Reviews are self-selected and reflect an unknown mix of user histories; issue labels and severity judgments may be uncertain. The aggregates do not establish prevalence among all users, causation, or actual churn. Any cancellation mentioned in reviews is expressed intent only.

Coverage: 100000 completed of 100000 sample inputs. No full-corpus recommendation is established.
Human inspection of the argument and quote support remains required.

Review revision: assistant clarification of the original generated memo; no new model call, label change, ranking change or numerical claim. The original memo is preserved in the parent run directory.
