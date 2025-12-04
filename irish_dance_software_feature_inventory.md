# The Architecture of Tradition: A Strategic Blueprint and Technical Specification for OpenFeis

## Executive Summary

The ecosystem of Irish Dance competition management stands at a precipice. For decades, the administration of *Feiseanna* (local competitions) and *Oireachtais* (regional and major championships) has relied on a fragmented collection of proprietary web applications. These legacy systems—most notably FeisWorx, QuickFeis, iFeis, and the recently destabilized GoFeis—serve as the operational backbone for an art form that is as logistically complex as it is culturally significant. The recent catastrophic failure of the GoFeis platform during a major championship event, the Mid-America Oireachtas (MAO) 2025, has exposed deep systemic fragilities in the current technological infrastructure. The incident, characterized by data synchronization failures, server crashes, and the inability to process results in real-time, left hundreds of dancers in distress and fundamentally eroded community trust in digital adjudication platforms.

This report serves as the foundational "bible" for the development of **OpenFeis**, an open-source initiative designed to return control, transparency, and unshakeable reliability to the Irish Dance community. To succeed where others have faltered, OpenFeis must transcend the definition of a mere registration form; it must function as a robust Enterprise Resource Planning (ERP) system specifically tailored to the idiosyncratic and rigid regulatory framework of *An Coimisiún le Rincí Gaelacha* (CLRG). It requires a sophisticated rules engine capable of handling complex age-grouping logic, a fault-tolerant tabulation system that functions autonomously without internet connectivity, and a user experience that accommodates the high-stress, high-volume environment of competition days.

The following analysis provides an exhaustive inventory of necessary features, rooted in a deep dissection of existing platforms and the regulatory framework of Irish Dance. It explores the mathematical intricacies of the "Irish Points" scoring system, the logistical complexities of schedule conflict detection, and the architectural requirements for "offline-first" resilience. This document is intended to guide the engineering of a system that is not merely a replacement but an evolution—stabilizing the present while enabling the future of the sport.

## Section 1: The Crisis of Confidence and the Operational Landscape

To engineer a solution for Irish Dance, one must first understand the hierarchy, the distinct user personas that interact with the system, and the specific failure modes that have plagued the community. A *Feis* is not a standard ticketed event; it is a multi-stage, multi-track competition governed by a rigid, global rulebook that varies slightly by region (e.g., North American Feis Commission vs. regional bodies in the UK or Australia). The failure of GoFeis was not simply a server outage; it was a failure to understand the mission-critical nature of tabulation data in a live competitive environment.

### 1.1 The Anatomy of Failure: The GoFeis Incident
The catalyst for the OpenFeis initiative is the recent breakdown of GoFeis during high-stakes events. Analysis of community feedback indicates that the failure was multifaceted. During the Mid-America Oireachtas 2025, a premier qualifying event, the system suffered from severe latency and eventual collapse during the critical results processing window. Reports confirm that recalls (lists of dancers advancing to the final round) were being announced verbally or via disparate social media channels because the central tabulation system was inaccessible.[1]

The operational impact was devastating:
*   **Data Lock:** Adjudicators could not submit scores, or scores submitted were not syncing to the central database.
*   **Calculation Paralysis:** The tabulation engine failed to process the complex "drop high/low" logic required for 5-judge panels, delaying awards ceremonies until the early hours of the morning.[2]
*   **Communication Blackout:** Parents and teachers were left in the dark, unable to access schedules or results, leading to chaos in the venue halls.

The architectural implication for OpenFeis is clear: **dependency on continuous internet connectivity and centralized cloud processing is a fatal flaw.** A robust system must operate on a "Local-First" architecture, where the venue's local network handles all critical path operations (scoring, tabulation, scheduling), and the cloud is used only for data backup and public dissemination.

### 1.2 The Stakeholder Matrix: A Four-Pillar User Base
The software must serve four distinct masters, often with conflicting needs. Understanding these personas is critical to designing the UI/UX and backend permissions logic.

#### 1.2.1 The Feis Organizer (The Administrator)
Usually a volunteer committee or a dance school (e.g., the TCRG and their booster club), their primary success metrics are speed of execution and financial reconciliation. They are not technical experts. They need to generate the "Syllabus" (the menu of competitions), manage caps (maximum number of entrants per competition), and ensure the event breaks even. They require high-level dashboards and granular control over schedule timing. Their nightmare is a financial discrepancy or a scheduling conflict that leaves a stage empty for an hour.[3, 4] They essentially act as the CEO of a temporary corporation that exists for 48 hours.

#### 1.2.2 The Tabulator (The Data Architect)
A specialized professional hired to manage the scoring data. They require a system that is mathematically infallible. Their nightmare is a calculation error in a Championship recall. They need "God-mode" access to override scores, merge competitions, and generate audit trails for every point awarded. In the wake of GoFeis, they are the most skeptical users; they will demand proof that the math works before trusting the system.[5] They are often the ones printing the recall sheets and handling the physical logistics of the result data.

#### 1.2.3 The Adjudicator (The End User)
The judges who sit at the tables for 8-10 hours straight. They need an interface that is distraction-free, high-contrast (stages are often dark), and incredibly fast. They cannot be slowed down by "loading" spinners or complex navigation. Their interface must mimic the paper "mark sheets" they have used for decades to minimize cognitive load. If the software lags, they will revert to paper, breaking the digital workflow.[6, 7]

#### 1.2.4 The Customer (Parents and Teachers)
Parents manage the accounts, pay the fees, and track results. Teachers need visibility into their entire school's registration to ensure students are entered in the correct levels. The user experience here centers on clarity of eligibility—preventing a "Beginner" from accidentally registering for an "Open Championship," which would result in disqualification and wasted fees.[3, 8]

## Section 2: The Regulatory Framework and Business Logic

The software cannot simply allow users to create events; it must enforce the laws of the sport. The *An Coimisiún le Rincí Gaelacha* (CLRG) sets the global standard, but the North American Feis Commission (NAFC) applies specific overlays for events in the US and Canada. The OpenFeis "Rules Engine" must be flexible enough to handle these regional variances.

### 2.1 The Chronology of Age
One of the most confusing aspects for new parents—and a critical logic requirement for the software—is age calculation.
*   **The "Jan 1" Rule:** Age groups are determined by the dancer's age on January 1st of the competition year. A dancer born on January 1, 2010, competes as "Under 14" for the entire year of 2024 (assuming the competition year is 2024). The software must automatically calculate this "competition age" based on the birthdate stored in the dancer's profile to prevent entry errors.[9]
*   **The "Wiggle Room":** While the rule is strict, the system must allow for manual overrides in edge cases (e.g., a dancer competing up an age group to fill a team).
*   **Yearly Rollover:** The system must automatically "age up" every dancer in the database on January 1st of the new year, adjusting their eligibility for the upcoming season.[3]

### 2.2 The Hierarchy of Proficiency
Dancers move through a progression of grades: Beginner, Advanced Beginner, Novice, Prizewinner, Preliminary Championship, and Open Championship.
*   **Advancement Logic:** The rules for moving up are algorithmic but complex.
    *   *Beginner to Advanced Beginner:* Often requires a 1st place win.
    *   *Novice to Prizewinner:* In some regions, winning a 1st place in Novice forces the dancer to move to Prizewinner for *that specific dance only*.
    *   *Preliminary to Open Championship:* This is the major threshold. Typically, winning two Preliminary Championships moves the dancer to Open for *all dances*. However, the NAFC rules state that if the second win occurs in the same calendar year as the first, the move is mandatory at the start of the next year, whereas CLRG rules might differ slightly.[10, 11]
*   **The "Sandbagging" Prevention:** The system needs a feature to track a dancer's placement history. If a dancer has won out of a grade, the system should technically block them from registering for that lower grade again. Current systems rely largely on the "honor system" or teacher oversight; OpenFeis could revolutionize this with a centralized advancement database.[12]

## Section 3: Competitive Analysis of Legacy Systems

To build a better system, OpenFeis must assimilate the strengths of the incumbents while structurally eliminating their weaknesses.

### 3.1 FeisWorx: The Utilitarian Standard
FeisWorx is widely regarded as the most stable and feature-complete option for North American organizers. Its strength lies in its rigid enforcement of syllabus rules and its deep administrative toolkit.
*   **Core Strength: Syllabus-Driven Filtering.** When a parent logs in, FeisWorx filters the thousands of available competitions down to the <10% the dancer is actually eligible for based on age and level.[3] This prevents "illegal" entries and reduces support tickets for organizers.
*   **Critical Feature:** **Family Maximums.** Many Feiseanna utilize a "Family Max" pricing model to keep the sport affordable. For example, entry fees might be capped at $150 per family, regardless of how many dances the children enter. FeisWorx calculates this dynamically in the shopping cart, a complex logic that involves excluding certain "special" fees (like venue levies or merchandise) from the cap.[13]
*   **UI/UX Weakness:** The interface is dated, web-centric, and lacks a responsive mobile app experience for real-time stage management.

### 3.2 QuickFeis: The Mobile Innovator
QuickFeis differentiates itself with a focus on the "day-of" experience, specifically through its mobile app for parents.
*   **Core Strength: Real-Time Stage Scheduling.** The QuickFeis app allows parents to see which competition is currently on stage and receive push notifications when their dancer is due. This alleviates the crowding around paper schedules taped to walls and is a beloved feature among parents.[14, 15]
*   **Critical Feature:** **Competitor Cards.** QuickFeis generates printable competitor number cards with QR codes or barcodes. These drive the check-in process and allow judges/stage monitors to quickly identify dancers. OpenFeis must implement a similar card generation module.[16, 17]

### 3.3 iFeis and FeisFWD: The Multimedia Niche
These platforms emerged strongly during the pandemic, offering "Video Feis" capabilities.
*   **Core Strength: Media Integration.** They facilitate the uploading of videos for remote adjudication. While in-person feiseanna are back, "hybrid" competitions or digital feedback rounds remain a valuable niche. iFeis also allows organizers to sell "highlight videos" created from the dancer's performance, adding a revenue stream.[5, 8]

## Section 4: Detailed Feature Inventory – The OpenFeis Bible

The following is a comprehensive specification of features required to achieve parity with legacy systems and surpass them in reliability. This inventory serves as the requirements document for the engineering team.

### 4.1 Module 1: The Syllabus & Configuration Engine
The Syllabus is the DNA of the event. If the syllabus setup is flawed, the registration and tabulation will fail. This module must be flexible enough to handle the infinite variations of local feis rules.

#### 4.1.1 Granular Competition Definition
The system must allow organizers to define competitions with extreme specificity. A "Competition" object in the database must support:
*   **Constraint Logic:**
    *   *Age Range:* Defined as min/max year of birth (e.g., Born 2014-2015).
    *   *Level:* Single level (Novice) or Merged levels (Novice/Prizewinner combined).
    *   *Gender:* Boys, Girls, or Mixed.
*   **Dance Requirement:**
    *   *Dance Type:* Reel, Slip Jig, Treble Jig, Hornpipe, Traditional Set, Modern Set, Treble Reel (Special).
    *   *Speed/Tempo:* Crucial for musicians. The system needs to display "Reel - 113bpm" to the stage monitor.[18]
    *   *Bars:* Number of bars to be danced (e.g., 32, 40, 48).
*   **Scoring Method:**
    *   *Solo:* 1 judge, 0-100 raw score.
    *   *Championship:* 3 or 5 judges, Irish Points conversion.
*   **Pricing Tier:** Differential pricing is standard. Solos might be $12, Preliminary Championships $45, and Open Championships $50. The system must support "flat fee" vs "per dance" pricing models.[13, 19]

#### 4.1.2 The "Syllabus Template" Engine
Organizers often run the same event annually. OpenFeis must allow "cloning" a previous year's syllabus, automatically incrementing the dates and adjusting age groups.
*   **Auto-Populate & Bulk Creation:** The system should pull standard CLRG rules to auto-populate competition lists. An organizer should be able to say "Generate all U8 to U18 Reel competitions for Prizewinner level," and the system should create those 11 database entries automatically.[13, 20]
*   **Merging & Splitting:** A critical admin tool. If "Under 9 Boys Reel" has only 1 entrant, the organizer needs a tool to merge it with "Under 10 Boys Reel." Conversely, if "Under 12 Girls Reel" has 50 entrants, it must be split into Group A and Group B (often by random assignment or birth month) to be manageable on stage.[21]

#### 4.1.3 Cap Management & Dynamic Waitlisting
Physical venues have fire codes and time limits.
*   **Hard Caps:** The system must enforce a global entrant cap (e.g., 2,500 dancers) and per-competition caps (e.g., 20 dancers per stage).
*   **Dynamic Waitlists:** When a cap is hit, users should be placed on a waitlist. If a registered dancer scratches (cancels), the system should optionally auto-email the next in line or auto-promote them.[22]

### 4.2 Module 2: The Registration Portal (Parent & Teacher Experience)
The user interface for parents must be foolproof to prevent mis-entry, which causes headaches for tabulators later.

#### 4.2.1 The "Dancer Resume"
Instead of re-entering data for every Feis, a parent creates a persistent "Dancer Resume" or profile.
*   **Fields:** Name, Date of Birth (validated against current date), School (linked to a registered Teacher account), Region (e.g., Mid-America), CLRG Registration Number.
*   **Level Tracking:** The system should track the dancer's level history. If a dancer wins out of Beginner, the system should prevent them from registering for Beginner at the next Feis. This "advancement tracking" is a major value-add over simple form-fillers.[3, 9]

#### 4.2.2 The Teacher Oversight Portal
Teachers are the gatekeepers of integrity and often the ones handling bulk payments for school-sponsored events.
*   **Roster Visibility:** Teachers must be able to log in and see a roster of all their students registered for a specific Feis.
*   **Flagging System:** A teacher should be able to "flag" an entry as incorrect (e.g., "Little Mary is not ready for Prelim"). This flag alerts the organizer and the parent.
*   **Bulk Registration:** For school figures (Ceili teams), teachers often register multiple teams at once. The system needs a bulk-entry interface for Ceili competitions.[8]

#### 4.2.3 The Financial Engine
The cart logic in Irish Dance is surprisingly complex.
*   **Family Maximums:** As noted in the FeisWorx analysis, the system must calculate the "Family Max" cap. It must distinguish between "Qualifying Fees" (registration fees that count toward the cap) and "Non-Qualifying Fees" (venue levies, late fees, T-shirt purchases, or charity donations which do *not* count toward the cap).[13]
*   **Late Fee Logic:** Automatic application of late fees after a specific timestamp.
*   **Change Fees:** Charging a fee (e.g., $10) for changing a competition level after the schedule is published.
*   **Refund Logic:** "Scratch" processing with partial refunds. The system needs to support "Credit Future Feis" or "Refund to Card" options.[13]

### 4.3 Module 3: Scheduling & Conflict Detection
This is the most computationally complex module and a major pain point for organizers. A typical Feis might have 5-8 stages running simultaneously from 8 AM to 5 PM.

#### 3.3.1 The Visual Scheduler (The "Gantt" View)
Organizers need a drag-and-drop interface to assign competitions to stages.
*   **Time Estimation:** The system must estimate competition duration based on specific formulas:
    *   *(Number of Dancers) × (bars of music) ÷ (dancers per rotation) + (setup time).*
    *   *Example Formula:* 50 dancers doing a 32-bar Reel, 2 at a time = approx 25 minutes.
*   **Load Balancing:** Visual indicators showing if Stage 3 is overloaded (ending at 8 PM) while Stage 1 finishes at 2 PM, allowing the organizer to drag competitions to balance the load.[4]

#### 3.3.2 Conflict Detection Algorithms
The "Nightmare Scenario" is a family with three children dancing on three different stages at the same time, or a dancer registered for both a Solo and a Team dance that overlap.
*   **Sibling Conflict:** The scheduler should flag time blocks where a single Family ID has dancers on multiple stages simultaneously. While not always avoidable, organizers try to minimize this.
*   **Teacher Conflicts:** A critical rule in CLRG is that an adjudicator cannot judge their own students (or students of their associates). The scheduler **must** cross-reference the Adjudicator's profile (and their associated school) against the school affiliation of the dancers in the competitions assigned to them. If a conflict is found (e.g., Judge A from School X is assigned to the "Under 12 Girls" where 5 dancers from School X are entered), the system must throw a critical alert.[18, 23]

### 4.4 Module 4: On-Site Operations & Offline Resilience
The breakdown of GoFeis proves that reliance on cloud connectivity is a fatal flaw. OpenFeis must adopt a "Local-First" architecture.

#### 4.4.1 The "Air-Gapped" Tabulation Architecture
*   **The "Server in a Box":** The organizer creates a local instance of the database on a laptop/server at the venue. This local server runs the tabulation logic.
*   **Tablet Synchronization:** Adjudicator tablets connect to this local server via a local WiFi router (Intranet), *not* the internet. This ensures that even if the venue's ISP goes down (a common occurrence in hotels/convention centers), the competition continues uninterrupted.
*   **Cloud Burst:** The local server pushes batched results to the cloud only when connectivity is available, for public viewing. The "Source of Truth" remains the local server until the event concludes.[24, 25]

#### 4.4.2 Digital Check-In and Stage Management
*   **QR Scanning:** Volunteers scan a dancer's number card at the side of the stage to mark them "Present." This updates the judge's tablet in real-time, highlighting the dancer on their grid.
*   **No-Show Management:** If a dancer is marked "Absent," the system removes them from the scoring grid, preventing judges from accidentally scoring an empty spot.

## Section 5: The Adjudication & Tabulation Engine (The "Black Box")

This section details the most critical logic of the application: scoring. In Irish Dance, scoring is not a simple summation. It involves raw scores, grid conversions, and complex algorithms for multi-judge panels. This is where OpenFeis must be mathematically perfect.

### 5.1 The Adjudicator's Interface (Tablet App)
This interface replaces the clipboard and pen. It must be mistake-proof and mimic the tactile speed of paper.
*   **Grid Layout:** A grid of dancer numbers. The judge taps a box to enter a score.
*   **Input:** Large, touch-friendly number pad for entering the "Raw Score" (0-100).
*   **Validation:** The system should prevent duplicate scores (e.g., two dancers getting 88) unless explicitly allowed by the specific competition rules (ties are often discouraged in raw scores).
*   **Comment Bank:** A library of predefined comments (e.g., "Cross feet," "Turnout," "Timing," "Carriage") that judges can tap to give feedback rapidly. This speeds up the process significantly compared to writing by hand.[8, 26]
*   **"Bell" Button:** A digital disqualification marker. If a dancer falls or stops, the judge hits the bell. The system must record this and automatically assign 0 points or the lowest possible rank depending on the rule enforced.[7]

### 5.2 The Mathematics of Irish Points (The 100-Point System)
The defining characteristic of Irish Dance scoring is the conversion of rank to "Irish Points." OpenFeis must implement this lookup table hard-coded into its logic. It is not a linear scale.

**The Irish Point Grid (Standard CLRG):**

| Rank | Irish Points | Rank | Irish Points | Rank | Irish Points |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1st | 100 | 6th | 53 | 11th | 41 |
| 2nd | 75 | 7th | 50 | 12th | 39 |
| 3rd | 65 | 8th | 47 | 13th | 38 |
| 4th | 60 | 9th | 45 |... |... |
| 5th | 56 | 10th | 43 | 50th | 1 |

*Note: The drop-off from 1st (100) to 2nd (75) is massive, designed to reward clear winners.* [27, 28]

**Mechanism:**
1.  **Raw Scoring:** Judge A gives Dancer X a raw score of 88.
2.  **Ranking:** The system ranks all raw scores for Judge A. Dancer X is ranked 2nd.
3.  **Conversion:** The system assigns 75 Irish Points to Dancer X for Judge A.
4.  **Aggregation:** This process is repeated for all judges (3 or 5), and the Irish Points are summed to determine the final winner.[27, 29]

### 5.3 Advanced Scoring Logic: Championship & Oireachtas
For major competitions, the scoring logic becomes multidimensional. This is the area where GoFeis likely struggled.

#### 5.3.1 The 5-Judge Panel (Oireachtas/Majors) - "The Drop Rule"
At regional championships (Oireachtas), panels often have 5 judges to ensure fairness. To prevent one biased judge from skewing the result, the **highest and lowest** scores are dropped.
*   **The Algorithm:**
    1.  Convert 5 Raw Scores to 5 Irish Point values.
    2.  Sort the Irish Point values (e.g., ).
    3.  Discard the top value (100) and bottom value (43).
    4.  Sum the remaining 3 values (60 + 65 + 75 = 200).
    5.  This "Net Score" determines the placement for that round.[30, 31]
*   *UI Insight:* OpenFeis must visualize this for the tabulator, highlighting the "dropped" scores in grey so they can verify the calculation manually if needed.

#### 5.3.2 The Recall Calculation (The 50% Rule)
In Championships, not everyone dances the final "Set Dance" round. The field is cut based on scores from Round 1 (Hard Shoe) and Round 2 (Soft Shoe).
*   **The Formula:** The system sums the Net Irish Points from Rounds 1 and 2.
*   **The Cut:** The top 50% of dancers (rounded up) qualify for Round 3.
*   **Tie Handling:** The system must handle the "unique dancer" count. If there are 100 dancers, 50 recall. If the 50th place is a 3-way tie, all three recall (52 dancers total). The software must auto-calculate this "Recall List" instantly to keep the event moving.[7, 32]

#### 5.3.3 Tie-Breaking Protocols
Ties are inevitable. The system must support configurable tie-breaking rules, as these vary by region:
*   **Option A:** Share the points (e.g., tie for 1st = (100+75)/2 = 87.5 points each).
*   **Option B:** Look at raw scores (sum of raw marks).
*   **Option C:** Borda Count / Median Rank analysis (used in some major championships).[33]

### 5.4 Tabulation Reports & Integrity
The "God View" for tabulators.
*   **The Grid Report:** A massive matrix showing every dancer (rows) and every judge's raw score/rank/IP (columns).
*   **Discrepancy Highlighting:** The system should auto-flag statistical anomalies (e.g., Judge A gave a dancer 100 [1st place], but Judge B gave them 60 [4th place]). This protects against "clerical errors" or bias.[27]

## Section 6: Results & Post-Event Experience

The immediate availability of results is the primary demand of parents and the single biggest failure point of legacy systems.

### 6.1 Real-Time Results Portal
*   **Live Feed:** As soon as a competition is "closed" by the tabulator, results should push to the public API.
*   **Detailed Scoresheets:** Parents essentially "buy" their feedback. The system should generate a PDF for each dancer showing their raw scores, ranks, and judge comments. This is a key revenue driver for Feiseanna; organizers often bundle "results" into the entry fee or sell them separately.[5, 27]

### 6.2 Teacher Data Exports
*   **School Summary:** Teachers receive a bulk export of all their students' placements. This data is used to update the school's internal tracking for advancement (e.g., "Mary moved out of Novice today"). OpenFeis could automate this, updating the global "Dancer Resume" directly.[8]

## Section 7: Future-Proofing – Features They Didn't Know to Ask For

To truly be a "gift" to the community, OpenFeis should innovate beyond mere replication.

1.  **AI Schedule Optimization:** Use historical data to predict exactly how long 50 Beginner Reels will take vs. 50 Open Champ Sets (which take much longer). Current estimates are manual guesses. An AI engine could auto-generate the most efficient stage schedule to minimize downtime and prevent the "10 PM finish" that plagues many events.[34]
2.  **Federated Advancement Tracking:** Currently, if a dancer moves regions (e.g., USA to UK), their "level" history is often lost or manual. OpenFeis could offer a "Global Dancer ID" (via blockchain or centralized ledger) that tracks level status universally, preventing "sandbagging" (dancing down a level) at inter-regional events.[12]
3.  **Integrated Music Player:** For the audio technician, integrate the music playlist directly into the stage management app. When the stage monitor clicks "Start U10 Reel," the audio system automatically cues the Reel track at 113bpm. This eliminates the common error of playing the wrong speed music.[35]

## Section 8: Technical Architecture & Security

### 8.1 Data Security & Compliance
*   **Minor Safety:** The system handles names and birthdates of minors. It must be GDPR and COPPA compliant. Dancers' names must be pseudonymized or hidden from adjudicators (Blind Adjudication).
*   **Role-Based Access Control (RBAC):** Adjudicators must *never* see the names of dancers, only their numbers. Tabulators see everything. Teachers see only their school. The architecture must enforce these silos rigorously.[36, 37]

### 8.2 Resilience Strategy
*   **Queue-Based Load Leveling:** Registration opening day acts like a DDoS attack. Parents spam "refresh" to get limited spots. The registration module should use a queue system to handle traffic spikes without crashing the database.
*   **Data Partitioning:** Each Feis should be logically isolated. A crash in the "Mid-America Oireachtas" database must never affect the "New York Feis" happening on the same day.

## Conclusion

The failure of GoFeis was a wake-up call that the Irish Dance community requires software that prioritizes engineering rigor over aesthetic novelty. The market is currently served by aging utilities (FeisWorx) or unstable innovators. By implementing the **"Local-First"** tabulation architecture, rigid **CLRG rule enforcement**, and the complex **5-judge/drop-score algorithms** detailed in this report, OpenFeis has the potential to become the new standard.

The bar may be "on the floor" in terms of current user satisfaction, but the technical bar for a system that manages thousands of concurrent data points in a disconnected environment, enforces draconian rule sets, and handles the emotional weight of championship results is exceptionally high. This specification provides the blueprint to clear that height. The community does not just need a new website; it needs a digital infrastructure that respects the precision, tradition, and passion of the sport it serves.