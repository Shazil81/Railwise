# Seeded railway routes

112 static train references, 486 distinct stations and 2,299 route-stop records.
Snapshots captured on 19 and 22 October 2026. Search reads only the local database.
These are saved timetables, not live services, official fares or real railway seat availability.

## Patna to Howrah coverage

The exact PNBE → HWH corridor includes 10 regular services across the weekly timetable. All 10 are not daily. Origin running days are shifted by the boarding stop day offset when searching.
Coverage is recorded in `backend/bookings/data/route_coverage.json`. The reviewed [source listing](https://etrain.info/trains/Patna-Jn-PNBE-to-Howrah-Jn-HWH) also includes nearby terminals and limited-date special trains; those must not be presented as permanent PNBE–HWH services.
Two special services are included with origin-date validity: 02024 (8 March–13 December 2026) and 04052 (2 October–29 November 2026). They appear only on their running days and inside those saved windows. This snapshot does not guarantee every current or future special train.
The source's exact PNBE/HWH station-code list was cross-checked on 22 October 2026: all 12 listed services are bundled, with zero missing. Nearby-terminal rows are excluded from that comparison.

Rajendra Nagar (RJPB), Patliputra (PPTA), Kolkata (KOAA), Sealdah (SDAH), Shalimar (SHM) and Santragachi (SRC) remain separate searchable stations. Choose the exact terminal from suggestions.

## All imported services

| Train | Name | From | To | Stops | Origin running days | Valid origin dates |
|---|---|---|---|---:|---|---|
| 12566 | BIHAR S KRANTI | New Delhi (NDLS) | Darbhanga Jn (DBG) | 16 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12306 | KOLKATA RAJDHNI | New Delhi (NDLS) | Howrah Jn (HWH) | 9 | Fri | Regular –  |
| 22348 | VANDE BHARAT EXP | Patna Jn (PNBE) | Howrah Jn (HWH) | 11 | Mon, Tue, Thu, Fri, Sat, Sun | Regular –  |
| 22436 | VANDE BHARAT EX | New Delhi (NDLS) | Varanasi Jn (BSB) | 4 | Mon, Tue, Wed, Fri, Sat, Sun | Regular –  |
| 12004 | SHATABDI EXPRESS | New Delhi (NDLS) | Lucknow Ne (LJN) | 9 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12951 | NDLS TEJAS RAJ | Mumbai Central (MMCT) | New Delhi (NDLS) | 8 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12952 | MMCT TEJAS RAJ | New Delhi (NDLS) | Mumbai Central (MMCT) | 8 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12957 | SBIB NDLS RAJ | Sabarmati Bg (SBIB) | New Delhi (NDLS) | 10 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12958 | SWRAN J RAJDHANI | New Delhi (NDLS) | Sabarmati Bg (SBIB) | 10 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12015 | AJMER SHATABDI | New Delhi (NDLS) | Daurai (Ajmer) (DOZ) | 11 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12016 | AII NDLS SHATBI | Daurai (Ajmer) (DOZ) | New Delhi (NDLS) | 11 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12627 | KARNATAKA EXP | Ksr Bengaluru (SBC) | New Delhi (NDLS) | 35 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12628 | KARNATAKA EXP | New Delhi (NDLS) | Smvt Bengaluru (SMVB) | 33 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12723 | TELANGANA SF EXP | Hyderabad Decan (HYB) | New Delhi (NDLS) | 18 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12724 | TELANGANA EXP | New Delhi (NDLS) | Hyderabad Decan (HYB) | 16 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12839 | CHENNAI MAIL | Santragachi Jn (SRC) | Mgr Chennai Ctr (MAS) | 35 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12840 | MAS HWH SF MAIL | Mgr Chennai Ctr (MAS) | Howrah Jn (HWH) | 36 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12007 | MAS MYS SHATABDI | Mgr Chennai Ctr (MAS) | Mysore Jn (MYS) | 4 | Mon, Tue, Wed, Fri, Sat, Sun | Regular –  |
| 12008 | SHATABDI EXP | Mysore Jn (MYS) | Mgr Chennai Ctr (MAS) | 4 | Mon, Tue, Wed, Fri, Sat, Sun | Regular –  |
| 12123 | DECCAN QUEEN | C Shivaji Maharaj T (CSMT) | Pune Jn (PUNE) | 5 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12124 | DECCAN QUEEN | Pune Jn (PUNE) | C Shivaji Maharaj T (CSMT) | 4 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12859 | GITANJALI EXP | C Shivaji Maharaj T (CSMT) | Howrah Jn (HWH) | 28 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12860 | GITANJALI EXP | Howrah Jn (HWH) | C Shivaji Maharaj T (CSMT) | 26 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12001 | NDLS SHATABDI | Rani Kamlapati(Bhopal) (RKMP) | New Delhi (NDLS) | 11 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12002 | SHATABDI EXPRES | New Delhi (NDLS) | Rani Kamlapati(Bhopal) (RKMP) | 11 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12505 | NORTHEAST EXP | Kamakhya (KYQ) | Anand Vihar Terminal (ANVT) | 34 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12506 | NORTH EAST EXP | Anand Vihar Terminal (ANVT) | Kamakhya (KYQ) | 33 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12801 | PURUSHOTTAM SF | Puri (PURI) | Anand Vihar Terminal (ANVT) | 34 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12802 | PURUSHOTTAM EXP | Anand Vihar Terminal (ANVT) | Puri (PURI) | 33 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12625 | KERALA SF EXP | Thiruvananthapuram Central (TVC) | New Delhi (NDLS) | 44 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12626 | KERALA SF EXP | New Delhi (NDLS) | Thiruvananthapuram Central (TVC) | 43 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12925 | PASCHIM EXPRESS | Bandra Terminus (BDTS) | Amritsar Jn (ASR) | 41 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12926 | PASCHIM EXPRESS | Amritsar Jn (ASR) | Bandra Terminus (BDTS) | 41 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12305 | RAJDHANI EXPRES | Howrah Jn (HWH) | New Delhi (NDLS) | 9 | Sun | Regular –  |
| 22347 | VANDE BHARAT EXP | Howrah Jn (HWH) | Patna Jn (PNBE) | 11 | Mon, Tue, Thu, Fri, Sat, Sun | Regular –  |
| 12274 | HWH DURONTO EXP | NEW DELHI (NDLS) | HOWRAH JN (HWH) | 7 | Tue, Sat | Regular –  |
| 13042 | HIMGIRI EXPRESS | JAMMU TAWI (JAT) | HOWRAH JN (HWH) | 34 | Sun, Mon, Thu | Regular –  |
| 12024 | JANSHATABDI EXP | PATNA JN (PNBE) | HOWRAH JN (HWH) | 16 | Mon, Tue, Wed, Thu, Fri, Sat | Regular –  |
| 12304 | POORVA EXPRESS | NEW DELHI (NDLS) | HOWRAH JN (HWH) | 25 | Sun, Wed, Thu, Sat | Regular –  |
| 13036 | UPASANA EXPRESS | DEHRADUN (DDN) | HOWRAH JN (HWH) | 20 | Wed, Sat | Regular –  |
| 13038 | KUMBHA EXPRESS | DEHRADUN (DDN) | HOWRAH JN (HWH) | 25 | Sun, Mon, Tue, Thu, Fri | Regular –  |
| 12273 | NDLS DURONTO | HOWRAH JN (HWH) | NEW DELHI (NDLS) | 7 | Mon, Fri | Regular –  |
| 13041 | HIMGIRI EXPRESS | HOWRAH JN (HWH) | JAMMU TAWI (JAT) | 34 | Tue, Fri, Sat | Regular –  |
| 12023 | JANSHATABDI EXP | HOWRAH JN (HWH) | PATNA JN (PNBE) | 16 | Mon, Tue, Wed, Thu, Fri, Sat | Regular –  |
| 12303 | POORVA EXPRESS | HOWRAH JN (HWH) | NEW DELHI (NDLS) | 25 | Mon, Tue, Fri, Sat | Regular –  |
| 13035 | UPASANA EXP | HOWRAH JN (HWH) | DEHRADUN (DDN) | 20 | Tue, Fri | Regular –  |
| 13037 | KUMBHA EXPRESS | HOWRAH JN (HWH) | DEHRADUN (DDN) | 25 | Sun, Mon, Wed, Thu, Sat | Regular –  |
| 13128 | KOL GARIB RATH | ARA JN (ARA) | KOLKATA (KOAA) | 15 | Sun, Wed, Fri | Regular –  |
| 13127 | ARA GARIB RATH | KOLKATA (KOAA) | ARA JN (ARA) | 15 | Tue, Thu, Sat | Regular –  |
| 13122 | GCT KOAA EXP | GHAZIPUR CITY (GCT) | KOLKATA (KOAA) | 15 | Mon | Regular –  |
| 13121 | KOAA GCT EXPRESS | KOLKATA (KOAA) | GHAZIPUR CITY (GCT) | 15 | Sun | Regular –  |
| 12316 | ANANYA EXP | UDAIPUR CITY (UDZ) | KOLKATA (KOAA) | 22 | Mon | Regular –  |
| 12315 | ANANYA EXPRESS | KOLKATA (KOAA) | UDAIPUR CITY (UDZ) | 22 | Thu | Regular –  |
| 12318 | AKAL TAKHT EXP | AMRITSAR JN (ASR) | KOLKATA (KOAA) | 24 | Tue, Fri | Regular –  |
| 12317 | AKAL TAKHT EXP | KOLKATA (KOAA) | AMRITSAR JN (ASR) | 24 | Sun, Wed | Regular –  |
| 12326 | GURUMUKHI EXP | AMBANDAURA (AADR) | KOLKATA (KOAA) | 20 | Sat | Regular –  |
| 12325 | GURUMUKHI EXP | KOLKATA (KOAA) | AMBANDAURA (AADR) | 19 | Thu | Regular –  |
| 22198 | PRATHAM S SNGRM | V LAKSHMIBAI JHANSI (VGLJ) | KOLKATA (KOAA) | 19 | Fri | Regular –  |
| 22197 | PRATHAM S S EXP | KOLKATA (KOAA) | V LAKSHMIBAI JHANSI (VGLJ) | 19 | Sun | Regular –  |
| 22214 | DURONTO EXPRESS | PATNA JN (PNBE) | SHALIMAR (SHM) | 4 | Tue, Thu, Sat | Regular –  |
| 22213 | SHM PNBE DURONTO | SHALIMAR (SHM) | PATNA JN (PNBE) | 4 | Mon, Wed, Fri | Regular –  |
| 22588 | AMRIT BHARAT EXP | BANARAS (BNRS) | SEALDAH (SDAH) | 8 | Sun, Tue, Fri | Regular –  |
| 22587 | AMRIT BHARAT EXP | SEALDAH (SDAH) | BANARAS (BNRS) | 8 | Mon, Wed, Sat | Regular –  |
| 12909 | NZM GARIB RATH | BANDRA TERMINUS (BDTS) | H NIZAMUDDIN (NZM) | 8 | Tue, Thu, Sat | Regular –  |
| 12910 | BDTS GARIB RATH | H NIZAMUDDIN (NZM) | BANDRA TERMINUS (BDTS) | 8 | Sun, Wed, Fri | Regular –  |
| 12301 | KOLKATA RAJDHNI | HOWRAH JN (HWH) | NEW DELHI (NDLS) | 9 | Mon, Tue, Wed, Thu, Fri, Sat | Regular –  |
| 12302 | KOLKATA RJDHNI | NEW DELHI (NDLS) | HOWRAH JN (HWH) | 9 | Sun, Mon, Tue, Wed, Thu, Sat | Regular –  |
| 12381 | POORVA EXPRESS | HOWRAH JN (HWH) | NEW DELHI (NDLS) | 22 | Sun, Wed, Thu | Regular –  |
| 12382 | POORVA EXPRESS | NEW DELHI (NDLS) | HOWRAH JN (HWH) | 23 | Mon, Tue, Fri | Regular –  |
| 12009 | SHATABDI EXP | MUMBAI CENTRAL (MMCT) | AHMEDABAD JN (ADI) | 9 | Mon, Tue, Wed, Thu, Fri, Sat | Regular –  |
| 12010 | SHATABDI EXP | AHMEDABAD JN (ADI) | MUMBAI CENTRAL (MMCT) | 9 | Mon, Tue, Wed, Thu, Fri, Sat | Regular –  |
| 12259 | BKN DURONTO EXP | SEALDAH (SDAH) | BIKANER JN (BKN) | 12 | Sun, Mon, Wed, Thu | Regular –  |
| 12260 | SDAH DURONTO | BIKANER JN (BKN) | SEALDAH (SDAH) | 12 | Mon, Tue, Thu, Fri | Regular –  |
| 13006 | ASR HWH MAIL | AMRITSAR JN (ASR) | HOWRAH JN (HWH) | 60 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 13048 | VIBHUTI EXPRESS | PRAYAGRAJ RAMBAGH (PRRB) | HOWRAH JN (HWH) | 33 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 13005 | AMRITSAR MAIL | HOWRAH JN (HWH) | AMRITSAR JN (ASR) | 60 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 13047 | VIBHUTI EXPRESS | HOWRAH JN (HWH) | PRAYAGRAJ RAMBAGH (PRRB) | 33 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12352 | RJPB HWH EXPRESS | RJNDR NGR BIHAR (RJPB) | HOWRAH JN (HWH) | 22 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12351 | HWH-RJPB EXPRES | HOWRAH JN (HWH) | RJNDR NGR BIHAR (RJPB) | 22 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12953 | AUG KR RAJ EXP | MUMBAI CENTRAL (MMCT) | H NIZAMUDDIN (NZM) | 13 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12954 | AG KRANTI RJDHN | H NIZAMUDDIN (NZM) | MUMBAI CENTRAL (MMCT) | 13 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12903 | GOLDEN TEMPLE ML | BANDRA TERMINUS (BDTS) | AMRITSAR JN (ASR) | 34 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12904 | GOLDN TEMPLE ML | AMRITSAR JN (ASR) | BANDRA TERMINUS (BDTS) | 34 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12163 | CHENNAI EXPRESS | LOKMANYATILAK T (LTT) | CHENNAI CENTRAL (MAS) | 26 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12164 | CHENNAI EXP | CHENNAI CENTRAL (MAS) | LOKMANYATILAK T (LTT) | 25 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12615 | GRAND TRUNK EXP | CHENNAI CENTRAL (MAS) | NEW DELHI (NDLS) | 39 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12616 | GRAND TRUNK EXP | NEW DELHI (NDLS) | CHENNAI CENTRAL (MAS) | 38 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 11301 | UDYAN EXPRESS | C SHIVAJI TERM MUMBAI (CSMT) | KSR BANGALORE CY JN (SBC) | 33 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 11302 | UDYAN EXP | KSR BANGALORE CY JN (SBC) | C SHIVAJI TERM MUMBAI (CSMT) | 33 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12013 | AMRITSAR SHTBDI | NEW DELHI (NDLS) | AMRITSAR JN (ASR) | 8 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12014 | NDLS SHATABDI | AMRITSAR JN (ASR) | NEW DELHI (NDLS) | 8 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12657 | BANGALORE MAIL | CHENNAI CENTRAL (MAS) | KSR BANGALORE CY JN (SBC) | 7 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12658 | CHENNAI MAIL | KSR BANGALORE CY JN (SBC) | CHENNAI CENTRAL (MAS) | 8 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12607 | LALBAGH EXPRESS | CHENNAI CENTRAL (MAS) | KSR BANGALORE CY JN (SBC) | 13 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12608 | LALBAGH SF EXP | KSR BANGALORE CY JN (SBC) | CHENNAI CENTRAL (MAS) | 13 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12759 | CHARMINAR SF EXP | CHENNAI BEACH (MSB) | HYDERABAD DECAN (HYB) | 17 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12760 | CHARMINAR EXP | HYDERABAD DECAN (HYB) | CHENNAI BEACH (MSB) | 17 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12809 | HOWRAH MAIL | C SHIVAJI TERM MUMBAI (CSMT) | HOWRAH JN (HWH) | 45 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12295 | SANGHAMITRA EXP | SMVT BENGALURU (SMVB) | DANAPUR (DNR) | 36 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12296 | SANGHA MITRA EX | DANAPUR (DNR) | SMVT BENGALURU (SMVB) | 36 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12309 | RJPB RAJDHANI | RJNDR NGR BIHAR (RJPB) | NEW DELHI (NDLS) | 7 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12310 | RJPB RAJDHANI | NEW DELHI (NDLS) | RJNDR NGR BIHAR (RJPB) | 7 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12391 | SHRAMJEEVI EXP | RAJGIR (RGD) | NEW DELHI (NDLS) | 34 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12392 | SHRAMJEVI N EXP | NEW DELHI (NDLS) | RAJGIR (RGD) | 34 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12141 | LTT PPTA EXPRESS | LOKMANYATILAK T (LTT) | PATLIPUTRA (PPTA) | 19 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12142 | PPTA LTT EXP | PATLIPUTRA (PPTA) | LOKMANYATILAK T (LTT) | 18 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12555 | GORAKDAM EXPRES | GORAKHPUR JN (GKP) | BHATINDA JN (BTI) | 21 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12556 | GORAKDAM EXPRES | BHATINDA JN (BTI) | GORAKHPUR JN (GKP) | 21 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12423 | DBRT NDLS RAJDHANI | DIBRUGARH (DBRG) | NEW DELHI (NDLS) | 25 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 12424 | DBRT RAJDHANI | NEW DELHI (NDLS) | DIBRUGARH (DBRG) | 25 | Mon, Tue, Wed, Thu, Fri, Sat, Sun | Regular –  |
| 02024 | PNBE HWH SF SPL | PATNA JN (PNBE) | HOWRAH JN (HWH) | 16 | Sun | 2026-03-08 – 2026-12-13 |
| 04052 | NDLS HWH SPL | NEW DELHI (NDLS) | HOWRAH JN (HWH) | 22 | Sun, Tue, Fri | 2026-10-02 – 2026-11-29 |

## Useful searches

- Patna Jn (PNBE) → Howrah (HWH), and reverse.
- New Delhi (NDLS) ↔ Howrah (HWH); several saved services.
- Bengaluru (SBC) ↔ Chennai (MAS); Shatabdi, Lalbagh and Mail references.
- Rajendra Nagar (RJPB) ↔ Howrah (HWH) or New Delhi (NDLS).
- Mumbai LTT (LTT) ↔ Chennai (MAS), and Mumbai CSMT (CSMT) ↔ Pune (PUNE).
- Hyderabad (HYB) ↔ Chennai (MAS) or New Delhi (NDLS).
- New Delhi (NDLS) ↔ Amritsar (ASR).
- Patliputra (PPTA) ↔ Mumbai LTT (LTT).

All intermediate stops are searchable in route order. Rerunning `seed_data` never resets existing bookings. The seed and runtime need no railway API key.
Per-train `snapshot_source` records public timetable provenance for the new 77 services. Two unavailable train numbers and one midnight-halt schedule were rejected by validation, rather than guessed.

## Expansion validation — 22 October 2026

- Both configured local databases migrated through `0010_train_service_validity` and seeded with 112 services. Existing bookings were preserved.
- Final 16 catalogue/coverage/reservation tests passed, including network-blocked search across a full week, major-corridor alternatives, repeat seeding, special-service origin-date validity and boarding-day offsets.
- The earlier 19 catalogue/local-engine checks also passed during expansion.
- Actual frontend-proxy API responses for PNBE–HWH returned 6 trains on 23 October, 8 on 24 October and 7 on 25 October 2026.
- Runtime railway discovery uses only the local DB; source requests were development-time imports only. No new live provider dependency was added.
