# Halqa: demonstration video script (5 minutes at most)

**Status: draft. The lead will validate every click against the running app before filming.** Control and screen names below are taken from the English locale files in `frontend/src/i18n/locales/en` and from the code in `frontend/src/features`. The author of this script has not run the app. Where a name or an order may differ on screen, trust the screen and fix this file.

Everything shown is synthetic and simulated. Do not say or imply that the system has been clinically validated, that it improves outcomes, or that it is connected to any real system.

Running time: opening 0:15, part 1 1:45, part 2 1:50, part 3 0:50, closing 0:15. Total 4:55.

## Pre-flight checklist

1. Start the API with demo mode on (the default). Check `http://localhost:8000/api/health` answers.
2. Open the app at the landing page. Click **Reset demo data** and confirm in the dialog titled "Reset demo data". Wait for the toast "Demo data was reset."
3. Do not move the demo clock before filming. The seeded overdue case is already overdue after a reset.
4. Browser: Chrome or Edge, window about 1280 by 720, zoom 100 percent, one tab, no bookmarks bar. The patient screens sit inside a phone-like frame (maximum width 480), so they stay readable at this size. Close other notifications.
5. Language: do not set it by hand. Each persona signs in with its own language: Khalid in Arabic, Jean-Paul in French, staff in English. Part 1 switches Khalid to English with the demo bar **Language** control.
6. Start signed out, on the landing page. Every part after the first uses **Switch persona** on the demo bar.
7. Know two things before filming: the reading to type in part 3 is `185/115`, and the correct teach-back answer in both the app and the thread is the second option ("A raised reading to check again").
8. Every retake needs a fresh **Reset demo data**, because part 1 changes Khalid's case and part 3 changes Jean-Paul's.
9. Optional cutaway, not in the timing: the "How it works" page (link on the landing page, "How decisions are made").

## Opening (0:00 to 0:15)

Screen: the landing page, title "Close the loop after a raised blood pressure result".

Narration: "When a screening finds a raised blood pressure, the result is often issued and then nobody owns the next step. People are not told, referrals stall, and nobody sees it is late. This is Halqa, a prototype that gives every raised result one case, one owner and one due date. Everything you will see is synthetic."

## Part 1: patient in Abu Dhabi (0:15 to 2:00)

| Beat | Click | The viewer should see | Narration | Time |
|---|---|---|---|---|
| 1.1 | **Continue as Guest**, then the card for **Khalid** ("Sign in as Khalid") | The patient app opens in Arabic, right to left, with the demo bar showing "Simulated data" | "Khalid is thirty-four. He was flagged at a simulated screening. The app opens in Arabic." | 0:08 |
| 1.2 | Demo bar **Language**, choose English | The same home screen in English: "Hello, Khalid", "Your reading" 152/96 | "He can switch to English at any time." | 0:10 |
| 1.3 | **See your result** | "Your result" with the reading, "This is a raised reading that needs checking. It is not a diagnosis.", "What this means", "What this does not mean", "This is not an emergency" | "The result says what it means and what it does not mean. It is a raised reading that needs checking. It is not a diagnosis." | 0:15 |
| 1.4 | **Answer two quick questions**. On "Check your understanding": answer **No** to each warning sign, choose the second answer ("A raised reading to check again"), pick a confidence number, **Send my answer** | "Thank you. That is clear." | "He checks for warning signs, then answers one question about his result. This is teach-back. A wrong answer would get a simpler explanation, never a failure." | 0:20 |
| 1.5 | **Choose how to check again**, then **At home for a week**, **Save my choice**. In the "Demo aid" box click **Fill a sample week of readings** | "Your readings", the day count, "Average so far", then "You have given enough readings. A clinician will review them next." | "He chooses home monitoring. To save time, this demo aid adds a made-up week of readings. The average appears as they arrive." | 0:15 |
| 1.6 | Open **Demo shortcuts**. Click **Care team: review my readings**, then **Care team: send and accept referral** | Toasts that Dr Sara reviewed the readings and sent the referral and that Dr Omar accepted it | "In real life staff do these steps. These buttons sign in as the right staff member and use the real action, so every step is in the audit log." | 0:12 |
| 1.7 | **Referral and visit**. Pick a time slot, look at **Cover for this visit**, click **Book this visit** | Time slots, "Cover for this visit" with a covered line and "You pay nothing", "Cover and prices are simulated for this demo.", then "Your visit is booked" | "Before he books, he sees what is covered. The cover figures are simulated." | 0:13 |
| 1.8 | In **Demo shortcuts** click **Care team: record my visit**. Open **This week's action**. Choose **I could not this week**, click **Save my check-in** | The first action "Less salt" at full size, then the message "That is fine. Some weeks are like this. Next week's step is smaller", with no red and no streak | "After the visit, he gets one small action a week. If a week does not go to plan, the next step gets smaller. Nothing is reset and nobody is blamed." | 0:12 |

Fallback for part 1: if a shortcut button is disabled, read the reason under it ("Available later: ...") and do the step before it. If **Fill a sample week of readings** fails, add readings by hand in "Add a reading" (home readings at or above 135/85 on four different days, two per day) or skip to beat 1.6 and say that readings were added off camera. If **Book this visit** says no times are available, cut to beat 1.8 and say that his visit is booked. If the Arabic screen looks wrong, start in English and skip beat 1.2.

## Part 2: coordinator and clinicians (2:00 to 3:50)

| Beat | Click | The viewer should see | Narration | Time |
|---|---|---|---|---|
| 2.1 | Demo bar **Switch persona**, choose **Mariam**. On "Case queue" click the tabs **Overdue**, **Rejected**, **Unowned** | One overdue case, one case with the reason "Wrong clinic, needs nephrology review", one case showing "No owner". Each row has an owner or "No owner" and a due date | "Mariam is a care coordinator. Every case has an owner and a due date. Here is one overdue, one with a rejected referral, and one with no owner. Nothing sits unseen." | 0:20 |
| 2.2 | In "Simulate incoming result" click **Simulate severe result (185/115)**, then the tab **Urgent** | The message "A new urgent case ... was opened at the top of the urgent queue." and the new case first in the Urgent tab | "A simulated screening feed sends a severe reading. A fixed rule, not a model, marks it urgent. It goes to the top and a same-day clinician review is created." | 0:15 |
| 2.3 | **Switch persona**, choose **Dr Sara**. On "Clinician worklist" open the case under **Urgent reviews**, choose **Complete urgent review**, type a short note, **Complete review** | The urgent flag is cleared and the audit timeline shows who did it | "Dr Sara sees it in her worklist. Only a clinician can end the urgent flag, and the note is recorded." | 0:20 |
| 2.4 | Back on the worklist open a case under **Ready to close**. Choose **Close case** and, without filling anything, click **Close case** in the dialog. Then choose the evidence type **Blood pressure controlled**, pick a reading under **Pick a reading**, click **Close case** | First the message "The case was not closed." with the server's reason. Then "The case was closed." | "Closing is hard on purpose. With no evidence the system refuses. With an evidence type and a reading, a clinician closes the case. No timer and no rule can close a case." | 0:25 |
| 2.5 | **Switch persona**, choose **Dr Omar**. In **Open e-consults** open the row marked "Asked of me". In the e-consult card type an answer under **Your answer**, click **Send answer** | The question from Dr Sara, then "Your answer was sent." | "Dr Sara asked Dr Omar a question about a patient. He answers inside the case, so the conversation does not get lost." | 0:15 |
| 2.6 | **Switch persona**, choose **Programme analyst**. On "Outcome dashboard" show the **Live data** part, then scroll to **Simulation**. Change **Split by** once | "fewer than 5" in small cells, the notice "Simulated results on synthetic people", baseline beside "With the loop" | "The analyst sees totals only, and any group under five people is hidden. The simulation is built on synthetic people and mostly on our own assumptions. It shows what the system measures. It is not evidence that it works." | 0:15 |

Fallback for part 2: if the severe button does not show the new case at the top, refresh the queue and open the **Urgent** tab again. If there is no case under **Ready to close**, open any case in the "In care" state as Dr Sara and close it with the evidence type **Other clinical decision** and a note of ten or more characters. If the e-consult row is not under Dr Omar, open the worklist as Dr Sara and show the same case with the waiting message instead. If the dashboard does not load, show the "How it works" page for the same closing statement. Never skip the refused close in beat 2.4. It is the key safety moment, and if the dialog accepts an empty close, stop filming and tell the lead.

## Part 3: patient in Yaounde (3:50 to 4:40)

| Beat | Click | The viewer should see | Narration | Time |
|---|---|---|---|---|
| 3.1 | **Switch persona**, choose **Jean-Paul** | An SMS style thread in French with the first message, the contact and the step owner shown at the top. The interface is in French | "Jean-Paul is a taxi driver in Yaounde. He has no app. He is reached by text message in French, here shown as a simulated phone thread." | 0:10 |
| 3.2 | Click the quick reply for **1** (**Read**), then **2** (**No**) at the warning sign question, then the second option (**B**) at the teach-back question | The red-flag question, the teach-back question with options A, B and C, then the home monitoring instructions | "Replies are matched against a fixed table of numbers and letters. No model reads his messages. He is asked about warning signs, then the same teach-back question as in the app." | 0:20 |
| 3.3 | Open **Demo shortcuts** and click **Send a sample week of readings** | Readings arriving as typed replies, then the thread confirming each one | "He sends his home readings by text. The nurse, Clarisse, is the accountable owner of his case." | 0:10 |
| 3.4 | Type `185/115` in the box and click **Send** | A reply with the urgent message and the emergency instruction for Yaounde: go to the nearest emergency department | "If a reading is severe, he is told at once what to do, and a clinician review is created. The instruction comes from approved text, not from a model." | 0:10 |

Fallback for part 3: if the thread is empty, reset the demo data and sign in again. If a quick-reply button is missing, type the reply into the box (`1`, `2`, then the letter). If the interface is in English, switch the demo bar **Language** to French only if the lead wants French on screen. If **Send a sample week of readings** is disabled, the reason reads "after you reply 1 to your first message", so complete beat 3.2 first. Beat 3.4 is optional. Drop it first if time runs over.

## Closing (4:40 to 4:55)

Screen: the dashboard disclaimer, or the "How it works" page with the placeholder banner "Every threshold and service level is a placeholder".

Narration: "To be clear about what is real. The case engine, the rules, the closure gate and the audit log are real code with automated tests. The patients, the screening feed, the insurance cover, the text messages and the outcome numbers are simulated. Every threshold and service level is a placeholder that still needs clinician sign-off. This is a prototype, not a medical device."
