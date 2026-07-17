-- Petrofer Signup Group Backfill (SQL variant of scripts/backfill_petrofer_groups.py)
--
-- Company: 383e3338-9883-4b3e-8dd6-d32f9a58339f
-- Mapping: 210 emails, 593 (email,group) pairs
--
-- HOW TO USE (safe workflow):
--   1. Run the whole block up to (and including) the DRY-RUN SUMMARY
--   2. Inspect the counts — should be plausible
--   3. If OK, run the UPDATE + POST-UPDATE VERIFY
--   4. If still OK, run COMMIT;  (or ROLLBACK; to undo)
--
-- Idempotent: users already in a group are skipped (no duplicate ids).
-- Safe against email case/whitespace: match uses lower(trim(email)).

BEGIN;

CREATE TEMP TABLE _petrofer_mapping (email text, group_id text) ON COMMIT DROP;

INSERT INTO _petrofer_mapping (email, group_id) VALUES
    ('alexander.byczkowicz@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('alexander.byczkowicz@petrofer.com', '2900fbdf-1db3-490d-a243-afc847cb3ca2'),  -- Produktion und Logistik
    ('alexander.byczkowicz@petrofer.com', '416c83b7-3b6f-4cbe-8cf5-3e509bf6e9c4'),  -- Logistik
    ('alexander.pott@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('alexander.pott@petrofer.com', '547ddddd-3143-4cf1-ac90-c3951028725e'),  -- Informations- und Organisationsmanagement
    ('alexander.pott@petrofer.com', 'e7eda362-2b2a-4793-ba99-e4662d0008a0'),  -- IT
    ('ali.siala@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('ali.siala@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('ali.siala@petrofer.com', 'cb660fc0-9dce-4a9d-846b-2979beda2ee3'),  -- F&E 2 Wärmebehandlung
    ('alice.friedrich@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('alice.friedrich@petrofer.com', '30e5d414-3ca8-4dfb-8201-a8a562e3a98c'),  -- Finanzen
    ('alkan.solak@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('alkan.solak@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('alkan.solak@petrofer.com', '019069a9-556a-4831-9ffb-76a502f47d49'),  -- F&E 1 Gießereitechnik
    ('andre.koenig@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('andre.koenig@petrofer.com', '547ddddd-3143-4cf1-ac90-c3951028725e'),  -- Informations- und Organisationsmanagement
    ('andre.koenig@petrofer.com', 'e7eda362-2b2a-4793-ba99-e4662d0008a0'),  -- IT
    ('andre.weber@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('andre.weber@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('andre.weber@petrofer.com', 'cb660fc0-9dce-4a9d-846b-2979beda2ee3'),  -- F&E 2 Wärmebehandlung
    ('andreas.hafke@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('andreas.hafke@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('andreas.hafke@petrofer.com', '8eba657b-f161-4441-905b-67cab7e8f387'),  -- F&E 3 Hydraulik und Schmierungstechnik Entwicklung
    ('andreas.klingenberg@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('andreas.klingenberg@petrofer.com', '2900fbdf-1db3-490d-a243-afc847cb3ca2'),  -- Produktion und Logistik
    ('andreas.klingenberg@petrofer.com', '8f3a70d1-bd62-4feb-9b56-69103a5ab7ad'),  -- Leitung Produktion und Logistik
    ('andreas.niesporek@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('andreas.niesporek@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('andreas.niesporek@petrofer.com', '8eba657b-f161-4441-905b-67cab7e8f387'),  -- F&E 3 Hydraulik und Schmierungstechnik Entwicklung
    ('andreas.scharf@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('andreas.scharf@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('andreas.scharf@petrofer.com', '59c37098-5649-4b64-99e8-d7efc07e074d'),  -- Region Nord-Ost
    ('andreas.schoener@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('andreas.schoener@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('andreas.schoener@petrofer.com', '4773b7db-e4f9-4160-84be-2f06ee7b9937'),  -- Region Süd
    ('anika.dybiona@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('anika.dybiona@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('anika.dybiona@petrofer.com', '8f9b6c68-5742-493e-8e3e-d5bc56bf2ac7'),  -- F&E 5 Industriereiniger und Korrosionsschutz
    ('anja.schubert@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('anja.schubert@petrofer.com', '8b55cade-3b3d-4a17-8422-65c08fe085e7'),  -- Personalmanagement
    ('anke.friedrici@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('anke.friedrici@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('anke.friedrici@petrofer.com', 'cb660fc0-9dce-4a9d-846b-2979beda2ee3'),  -- F&E 2 Wärmebehandlung
    ('anke.friedrici@petrofer.com', '926c643a-ea69-445f-84a1-bfb5e045198e'),  -- Leitung F&E 2 Wärmebehandlung
    ('annette.bleckmann@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('annette.bleckmann@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('annette.bleckmann@petrofer.com', 'f92903f4-1f5f-4c8b-8720-5a1153bdfacf'),  -- Export
    ('antje.neugebauer@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('antje.neugebauer@petrofer.com', '2a72c5a7-7f39-4709-b7e5-f1174331e34f'),  -- Einkauf
    ('artur.kawohl@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('artur.kawohl@petrofer.com', '3e12a594-e449-4c75-866f-0fe0b73379b1'),  -- Produktmanagement
    ('astrid.schrot@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('astrid.schrot@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('astrid.schrot@petrofer.com', '8eba657b-f161-4441-905b-67cab7e8f387'),  -- F&E 3 Hydraulik und Schmierungstechnik Entwicklung
    ('axel.hoffmann@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('axel.hoffmann@petrofer.com', '2900fbdf-1db3-490d-a243-afc847cb3ca2'),  -- Produktion und Logistik
    ('axel.hoffmann@petrofer.com', 'c7ce1b6b-05fb-4305-9d96-a2e91c65f25a'),  -- Produktion
    ('babette.petzold@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('babette.petzold@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('babette.petzold@petrofer.com', '01d40d0d-6ed9-46fc-aac3-ffa6ba8e357f'),  -- Innendienst
    ('birgit.duerkop@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('birgit.duerkop@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('birgit.duerkop@petrofer.com', '8eba657b-f161-4441-905b-67cab7e8f387'),  -- F&E 3 Hydraulik und Schmierungstechnik Entwicklung
    ('bjoern.knurr@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('bjoern.knurr@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('bjoern.knurr@petrofer.com', '4773b7db-e4f9-4160-84be-2f06ee7b9937'),  -- Region Süd
    ('burak.arsu@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('burak.arsu@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('burak.arsu@petrofer.com', 'a7fb09b0-b131-4c56-9776-23cc7d33716b'),  -- Region West-Mitte
    ('carola.schmalz@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('carsten.muehl@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('carsten.muehl@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('carsten.muehl@petrofer.com', '95327fd8-f5d4-4b00-81d9-9dd87fe9b869'),  -- Leitung Forschung und Entwicklung
    ('catrin.saffran-wagenleiter@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('catrin.saffran-wagenleiter@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('catrin.saffran-wagenleiter@petrofer.com', 'f92903f4-1f5f-4c8b-8720-5a1153bdfacf'),  -- Export
    ('charis.wiesbaum@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('charis.wiesbaum@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('charis.wiesbaum@petrofer.com', 'f4e83e06-a218-45c7-8a86-575c76198915'),  -- Sicherheitsdatentechnik
    ('christian.holzminden@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('christian.holzminden@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('christian.holzminden@petrofer.com', '2ce5e832-9292-424b-bc96-a6c3f29767f9'),  -- Leitung Vertrieb Metalworking Europe
    ('christiana.schulz@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('christiana.schulz@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('christiana.schulz@petrofer.com', '01d40d0d-6ed9-46fc-aac3-ffa6ba8e357f'),  -- Innendienst
    ('christoph.klinkowski-buehring@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('christoph.klinkowski-buehring@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('christoph.klinkowski-buehring@petrofer.com', '019069a9-556a-4831-9ffb-76a502f47d49'),  -- F&E 1 Gießereitechnik
    ('christoph.klinkowski-buehring@petrofer.com', 'b3a0d087-7b05-4f2a-8ade-6e9ca547da92'),  -- Leitung F&E 1 Gießereitechnik
    ('christoph.meister@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('christoph.meister@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('christoph.meister@petrofer.com', 'f48017b8-0e09-449c-8968-2e2b510154da'),  -- F&E 4 Zerspanung und Umformung
    ('christoph.meister@petrofer.com', '76eca97a-84ae-4a15-8910-efeb8eec78a4'),  -- Leitung F&E 4 Zerspanung und Umformung
    ('christoph.sachse@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('christoph.siegert@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('christoph.siegert@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('christoph.siegert@petrofer.com', '8f9b6c68-5742-493e-8e3e-d5bc56bf2ac7'),  -- F&E 5 Industriereiniger und Korrosionsschutz
    ('christopher.schulla@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('christopher.schulla@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('christopher.schulla@petrofer.com', 'a7fb09b0-b131-4c56-9776-23cc7d33716b'),  -- Region West-Mitte
    ('claudia.bolik@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('claudia.bolik@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('claudia.bolik@petrofer.com', '709907ec-7ce6-4552-b74e-ba3355c62120'),  -- Zentrale Analytik
    ('claudia.braune-krickau@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('claudia.braune-krickau@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('claudia.braune-krickau@petrofer.com', 'f92903f4-1f5f-4c8b-8720-5a1153bdfacf'),  -- Export
    ('constantin.fischer@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('constantin.fischer@petrofer.com', '975e8d9a-7a31-4bcd-b4a7-7c1a230a4299'),  -- Leitung Geschäftsführung CEO
    ('daniel.wehrmaker@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('daniel.wehrmaker@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('daniel.wehrmaker@petrofer.com', 'f48017b8-0e09-449c-8968-2e2b510154da'),  -- F&E 4 Zerspanung und Umformung
    ('david.roda@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('david.roda@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('david.roda@petrofer.com', '4a51362a-8f43-4540-b21a-6b9fd8ec41ec'),  -- Anwendungstechnik
    ('davor.djekic@petrofer.com', 'e4a81f2b-7e38-4081-b163-1b3f7bc6db53'),  -- Geschäftsführung Strategie
    ('davor.djekic@petrofer.com', 'b0757f1f-8c6d-4533-a461-2e8638c6eb52'),  -- Papierchemikalien
    ('denis.kraft@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('denis.kraft@petrofer.com', 'a4e22785-779b-46ad-b07b-8c34939d0406'),  -- Technik
    ('dennis.habi@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('dennis.habi@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('dennis.habi@petrofer.com', 'f48017b8-0e09-449c-8968-2e2b510154da'),  -- F&E 4 Zerspanung und Umformung
    ('dennis.krasson@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('dennis.krasson@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('dennis.krasson@petrofer.com', '4a51362a-8f43-4540-b21a-6b9fd8ec41ec'),  -- Anwendungstechnik
    ('dennis.maslakov@petrofer.com', 'e4a81f2b-7e38-4081-b163-1b3f7bc6db53'),  -- Geschäftsführung Strategie
    ('dennis.maslakov@petrofer.com', 'b0757f1f-8c6d-4533-a461-2e8638c6eb52'),  -- Papierchemikalien
    ('dennis.schuetze@petrofer.com', 'e4a81f2b-7e38-4081-b163-1b3f7bc6db53'),  -- Geschäftsführung Strategie
    ('dennis.schuetze@petrofer.com', 'b0757f1f-8c6d-4533-a461-2e8638c6eb52'),  -- Papierchemikalien
    ('dennis.stoffregen@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('dennis.stoffregen@petrofer.com', '2a72c5a7-7f39-4709-b7e5-f1174331e34f'),  -- Einkauf
    ('dieter.seipp@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('dieter.seipp@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('dieter.seipp@petrofer.com', 'a7fb09b0-b131-4c56-9776-23cc7d33716b'),  -- Region West-Mitte
    ('domenic-rene.sandvoss@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('domenic-rene.sandvoss@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('domenic-rene.sandvoss@petrofer.com', 'f48017b8-0e09-449c-8968-2e2b510154da'),  -- F&E 4 Zerspanung und Umformung
    ('dragan.djurdjevic@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('dragan.djurdjevic@petrofer.com', '2900fbdf-1db3-490d-a243-afc847cb3ca2'),  -- Produktion und Logistik
    ('dragan.djurdjevic@petrofer.com', 'c7ce1b6b-05fb-4305-9d96-a2e91c65f25a'),  -- Produktion
    ('evelina.harder@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('evelina.harder@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('evelina.harder@petrofer.com', '8eba657b-f161-4441-905b-67cab7e8f387'),  -- F&E 3 Hydraulik und Schmierungstechnik Entwicklung
    ('evelyn.labat@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('evelyn.labat@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('evelyn.labat@petrofer.com', 'f92903f4-1f5f-4c8b-8720-5a1153bdfacf'),  -- Export
    ('fabian.keck@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('fabian.keck@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('fabian.keck@petrofer.com', '8f9b6c68-5742-493e-8e3e-d5bc56bf2ac7'),  -- F&E 5 Industriereiniger und Korrosionsschutz
    ('felix.goebel@petrofer.com', 'e4a81f2b-7e38-4081-b163-1b3f7bc6db53'),  -- Geschäftsführung Strategie
    ('felix.goebel@petrofer.com', 'b0757f1f-8c6d-4533-a461-2e8638c6eb52'),  -- Papierchemikalien
    ('filiz.odaci@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('filiz.odaci@petrofer.com', '2900fbdf-1db3-490d-a243-afc847cb3ca2'),  -- Produktion und Logistik
    ('filiz.odaci@petrofer.com', '416c83b7-3b6f-4cbe-8cf5-3e509bf6e9c4'),  -- Logistik
    ('finn.blumberg@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('finn.blumberg@petrofer.com', '15f7da41-c840-4fac-b403-701bc12742ad'),  -- Marketing
    ('fischer-equity@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('florian.klassen@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('florian.klassen@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('florian.klassen@petrofer.com', '4a51362a-8f43-4540-b21a-6b9fd8ec41ec'),  -- Anwendungstechnik
    ('florian.klassen@petrofer.com', '83805a32-2e65-4cf6-8308-f448d323bc77'),  -- Leitung Anwendungstechnik
    ('florian.treptow@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('florian.treptow@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('florian.treptow@petrofer.com', '8f9b6c68-5742-493e-8e3e-d5bc56bf2ac7'),  -- F&E 5 Industriereiniger und Korrosionsschutz
    ('florian.treptow@petrofer.com', 'bbb393a8-bba5-4841-a1fc-9ae8ecfbd96f'),  -- Leitung F&E 5 Industriereiniger und Korrosionsschutz
    ('frank.adolf@petrofer.com', 'e4a81f2b-7e38-4081-b163-1b3f7bc6db53'),  -- Geschäftsführung Strategie
    ('frank.adolf@petrofer.com', 'b0757f1f-8c6d-4533-a461-2e8638c6eb52'),  -- Papierchemikalien
    ('frank.froese@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('frank.froese@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('frank.froese@petrofer.com', 'a7fb09b0-b131-4c56-9776-23cc7d33716b'),  -- Region West-Mitte
    ('frank.hornbostel@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('frank.hornbostel@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('frank.hornbostel@petrofer.com', '8f9b6c68-5742-493e-8e3e-d5bc56bf2ac7'),  -- F&E 5 Industriereiniger und Korrosionsschutz
    ('franziska.wehrheim@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('franziska.wehrheim@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('franziska.wehrheim@petrofer.com', 'b0d7510a-f0c2-4cb3-92af-5df3a82b7ac3'),  -- Global Key Account Management
    ('gabriele.kurzok@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('gabriele.kurzok@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('gabriele.kurzok@petrofer.com', '8f9b6c68-5742-493e-8e3e-d5bc56bf2ac7'),  -- F&E 5 Industriereiniger und Korrosionsschutz
    ('gesa-marie.fischer@petrofer.com', 'e4a81f2b-7e38-4081-b163-1b3f7bc6db53'),  -- Geschäftsführung Strategie
    ('gesa-marie.fischer@petrofer.com', 'bcd5573f-5e3a-4eb0-b51a-2119e595122f'),  -- Leitung Geschäftsführung Strategie
    ('gisela.pietruska@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('gisela.pietruska@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('gisela.pietruska@petrofer.com', 'cb660fc0-9dce-4a9d-846b-2979beda2ee3'),  -- F&E 2 Wärmebehandlung
    ('greta.stuempel@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('greta.stuempel@petrofer.com', '15f7da41-c840-4fac-b403-701bc12742ad'),  -- Marketing
    ('greta.stuempel@petrofer.com', '5292a75a-d977-4d4f-92e1-d3b633e3f0bf'),  -- Leitung Marketing
    ('grit.heunemann@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('grit.heunemann@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('grit.heunemann@petrofer.com', '709907ec-7ce6-4552-b74e-ba3355c62120'),  -- Zentrale Analytik
    ('halil.kenan@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('halil.kenan@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('halil.kenan@petrofer.com', '4773b7db-e4f9-4160-84be-2f06ee7b9937'),  -- Region Süd
    ('heiko.preusser@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('heiko.preusser@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('heiko.preusser@petrofer.com', 'b0d7510a-f0c2-4cb3-92af-5df3a82b7ac3'),  -- Global Key Account Management
    ('henning.reich@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('henning.reich@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('henning.reich@petrofer.com', '8f9b6c68-5742-493e-8e3e-d5bc56bf2ac7'),  -- F&E 5 Industriereiniger und Korrosionsschutz
    ('holger.ritter@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('holger.ritter@petrofer.com', '547ddddd-3143-4cf1-ac90-c3951028725e'),  -- Informations- und Organisationsmanagement
    ('holger.ritter@petrofer.com', 'e7eda362-2b2a-4793-ba99-e4662d0008a0'),  -- IT
    ('ina.hartmann@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('ina.hartmann@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('ina.hartmann@petrofer.com', '8eba657b-f161-4441-905b-67cab7e8f387'),  -- F&E 3 Hydraulik und Schmierungstechnik Entwicklung
    ('ingo.floerke@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('ingo.floerke@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('ingo.floerke@petrofer.com', '8eba657b-f161-4441-905b-67cab7e8f387'),  -- F&E 3 Hydraulik und Schmierungstechnik Entwicklung
    ('ismail.madrane@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('ismail.madrane@petrofer.com', '3e12a594-e449-4c75-866f-0fe0b73379b1'),  -- Produktmanagement
    ('janine.butterbrod@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('janine.butterbrod@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('janine.butterbrod@petrofer.com', 'f92903f4-1f5f-4c8b-8720-5a1153bdfacf'),  -- Export
    ('janine.butterbrod@petrofer.com', '3bb3a9f4-e9a8-4996-8992-ed88b0c54bc6'),  -- Leitung Export
    ('jeanie.kaiser@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('jeanie.kaiser@petrofer.com', '516caf26-dcd1-4b45-a79d-283723e942aa'),  -- Controlling
    ('jennifer.helmrich@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('jennifer.helmrich@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('jennifer.helmrich@petrofer.com', '8f9b6c68-5742-493e-8e3e-d5bc56bf2ac7'),  -- F&E 5 Industriereiniger und Korrosionsschutz
    ('jens.muench@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('jens.muench@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('jens.muench@petrofer.com', '4a51362a-8f43-4540-b21a-6b9fd8ec41ec'),  -- Anwendungstechnik
    ('jens.reichelt@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('jens.reichelt@petrofer.com', '547ddddd-3143-4cf1-ac90-c3951028725e'),  -- Informations- und Organisationsmanagement
    ('jens.reichelt@petrofer.com', '45e877f2-8bdb-4361-84d4-becf067b255b'),  -- Leitung Informations- und Organisationsmanagement
    ('jobst.klein@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('jobst.klein@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('jobst.klein@petrofer.com', 'b0d7510a-f0c2-4cb3-92af-5df3a82b7ac3'),  -- Global Key Account Management
    ('joerg.feilcke@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('joerg.feilcke@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('joerg.feilcke@petrofer.com', 'a7fb09b0-b131-4c56-9776-23cc7d33716b'),  -- Region West-Mitte
    ('jorrit.wolpers@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('jorrit.wolpers@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('jorrit.wolpers@petrofer.com', 'f48017b8-0e09-449c-8968-2e2b510154da'),  -- F&E 4 Zerspanung und Umformung
    ('julian.uhl@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('julian.uhl@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('julian.uhl@petrofer.com', '4773b7db-e4f9-4160-84be-2f06ee7b9937'),  -- Region Süd
    ('justus.meyer@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('justus.meyer@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('justus.meyer@petrofer.com', '8f9b6c68-5742-493e-8e3e-d5bc56bf2ac7'),  -- F&E 5 Industriereiniger und Korrosionsschutz
    ('jutta.teuber@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('jutta.teuber@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('jutta.teuber@petrofer.com', '709907ec-7ce6-4552-b74e-ba3355c62120'),  -- Zentrale Analytik
    ('kai.hemmerlein@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('kai.hemmerlein@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('kai.hemmerlein@petrofer.com', 'b0d7510a-f0c2-4cb3-92af-5df3a82b7ac3'),  -- Global Key Account Management
    ('karsten.brueckner@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('karsten.brueckner@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('karsten.brueckner@petrofer.com', '4a51362a-8f43-4540-b21a-6b9fd8ec41ec'),  -- Anwendungstechnik
    ('karsten.koch@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('karsten.koch@petrofer.com', '2900fbdf-1db3-490d-a243-afc847cb3ca2'),  -- Produktion und Logistik
    ('karsten.koch@petrofer.com', 'c7ce1b6b-05fb-4305-9d96-a2e91c65f25a'),  -- Produktion
    ('kay.ibenthal@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('kay.ibenthal@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('kay.ibenthal@petrofer.com', '8f9b6c68-5742-493e-8e3e-d5bc56bf2ac7'),  -- F&E 5 Industriereiniger und Korrosionsschutz
    ('kerstin.loehmann@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('kerstin.loehmann@petrofer.com', '30e5d414-3ca8-4dfb-8201-a8a562e3a98c'),  -- Finanzen
    ('kevin.rosenthal@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('kevin.rosenthal@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('kevin.rosenthal@petrofer.com', 'cb660fc0-9dce-4a9d-846b-2979beda2ee3'),  -- F&E 2 Wärmebehandlung
    ('khalid.aldughaim@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('khalid.aldughaim@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('khalid.aldughaim@petrofer.com', 'cb660fc0-9dce-4a9d-846b-2979beda2ee3'),  -- F&E 2 Wärmebehandlung
    ('konul.hidayatow@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('konul.hidayatow@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('konul.hidayatow@petrofer.com', 'cb660fc0-9dce-4a9d-846b-2979beda2ee3'),  -- F&E 2 Wärmebehandlung
    ('kora.fischer-kim@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('kora.fischer-kim@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('kristin.moehle@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('kristin.moehle@petrofer.com', '8b55cade-3b3d-4a17-8422-65c08fe085e7'),  -- Personalmanagement
    ('laila.nazari@petrofer.com', 'e4a81f2b-7e38-4081-b163-1b3f7bc6db53'),  -- Geschäftsführung Strategie
    ('laila.nazari@petrofer.com', 'b0757f1f-8c6d-4533-a461-2e8638c6eb52'),  -- Papierchemikalien
    ('lars.huntemann@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('lars.huntemann@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('lars.huntemann@petrofer.com', 'a7fb09b0-b131-4c56-9776-23cc7d33716b'),  -- Region West-Mitte
    ('lars.huntemann@petrofer.com', '178a5fc5-4b1e-45d4-af4f-9ce31f9a1547'),  -- Leitung Region West-Mitte
    ('laura.villani@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('laura.villani@petrofer.com', '8b55cade-3b3d-4a17-8422-65c08fe085e7'),  -- Personalmanagement
    ('leonard.eisner@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('leonard.eisner@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('leonard.eisner@petrofer.com', '8eba657b-f161-4441-905b-67cab7e8f387'),  -- F&E 3 Hydraulik und Schmierungstechnik Entwicklung
    ('liseth.rodenberg@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('liseth.rodenberg@petrofer.com', '2a72c5a7-7f39-4709-b7e5-f1174331e34f'),  -- Einkauf
    ('maj.demirezen@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('maj.demirezen@petrofer.com', 'a4e22785-779b-46ad-b07b-8c34939d0406'),  -- Technik
    ('maj.demirezen@petrofer.com', '611550d4-4b39-451d-b906-208b03010ec2'),  -- Anlagenmanagement
    ('marc.baum@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('marc.baum@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('marc.baum@petrofer.com', '709907ec-7ce6-4552-b74e-ba3355c62120'),  -- Zentrale Analytik
    ('marc.gasmus@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('marc.gasmus@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('marc.gasmus@petrofer.com', 'cb660fc0-9dce-4a9d-846b-2979beda2ee3'),  -- F&E 2 Wärmebehandlung
    ('marco.hirt@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('marco.hirt@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('marco.hirt@petrofer.com', 'a7fb09b0-b131-4c56-9776-23cc7d33716b'),  -- Region West-Mitte
    ('marco.klug@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('marco.klug@petrofer.com', '547ddddd-3143-4cf1-ac90-c3951028725e'),  -- Informations- und Organisationsmanagement
    ('marco.klug@petrofer.com', 'e7eda362-2b2a-4793-ba99-e4662d0008a0'),  -- IT
    ('marco.sendner@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('marco.sendner@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('marco.sendner@petrofer.com', 'b0d7510a-f0c2-4cb3-92af-5df3a82b7ac3'),  -- Global Key Account Management
    ('marco.sendner@petrofer.com', 'db4157ed-2309-46f9-b9b9-8047f15014df'),  -- Leitung Global Key Account Management
    ('marco.wendel@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('marco.wendel@petrofer.com', 'a4e22785-779b-46ad-b07b-8c34939d0406'),  -- Technik
    ('marco.wendel@petrofer.com', 'a9819947-2e92-490c-83af-a3735f64988f'),  -- Instandhaltung
    ('marco.wendel@petrofer.com', 'b76a13cc-f0c4-494c-b343-feb8d2732dd1'),  -- Leitung Instandhaltung
    ('marco.zint@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('marco.zint@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('marco.zint@petrofer.com', 'cb660fc0-9dce-4a9d-846b-2979beda2ee3'),  -- F&E 2 Wärmebehandlung
    ('marcus.amann@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('marcus.amann@petrofer.com', '2900fbdf-1db3-490d-a243-afc847cb3ca2'),  -- Produktion und Logistik
    ('marcus.amann@petrofer.com', 'c7ce1b6b-05fb-4305-9d96-a2e91c65f25a'),  -- Produktion
    ('marcus.both@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('marcus.both@petrofer.com', '516caf26-dcd1-4b45-a79d-283723e942aa'),  -- Controlling
    ('marcus.both@petrofer.com', '904bea85-0805-46ff-b146-ef36741d9d6e'),  -- Leitung Controlling
    ('mareike.wendel@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('mareike.wendel@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('mareike.wendel@petrofer.com', '01d40d0d-6ed9-46fc-aac3-ffa6ba8e357f'),  -- Innendienst
    ('margret.burgdorf@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('margret.burgdorf@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('margret.burgdorf@petrofer.com', '01d40d0d-6ed9-46fc-aac3-ffa6ba8e357f'),  -- Innendienst
    ('maria.castelli@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('maria.castelli@petrofer.com', '15f7da41-c840-4fac-b403-701bc12742ad'),  -- Marketing
    ('mario.luebker@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('mario.luebker@petrofer.com', '547ddddd-3143-4cf1-ac90-c3951028725e'),  -- Informations- und Organisationsmanagement
    ('mario.luebker@petrofer.com', 'e7eda362-2b2a-4793-ba99-e4662d0008a0'),  -- IT
    ('martin.bittner@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('martin.bittner@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('martin.bittner@petrofer.com', '709907ec-7ce6-4552-b74e-ba3355c62120'),  -- Zentrale Analytik
    ('martin.bittner@petrofer.com', 'e6e38901-fe70-489a-ada2-b61dfeb636ed'),  -- Leitung Zentrale Analytik
    ('martin.gisa@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('martin.gisa@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('martin.gisa@petrofer.com', '01d40d0d-6ed9-46fc-aac3-ffa6ba8e357f'),  -- Innendienst
    ('martin.meyer@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('martin.meyer@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('martin.meyer@petrofer.com', 'b0d7510a-f0c2-4cb3-92af-5df3a82b7ac3'),  -- Global Key Account Management
    ('martin.zarski@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('martin.zarski@petrofer.com', '2900fbdf-1db3-490d-a243-afc847cb3ca2'),  -- Produktion und Logistik
    ('martin.zarski@petrofer.com', '416c83b7-3b6f-4cbe-8cf5-3e509bf6e9c4'),  -- Logistik
    ('matthias.otto@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('matthias.otto@petrofer.com', '8b55cade-3b3d-4a17-8422-65c08fe085e7'),  -- Personalmanagement
    ('max.callegari@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('max.callegari@petrofer.com', 'a4e22785-779b-46ad-b07b-8c34939d0406'),  -- Technik
    ('max.callegari@petrofer.com', '9fc8149d-85ee-4e50-b989-579d0909ba20'),  -- Leitung Technik
    ('max.roesner@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('max.roesner@petrofer.com', 'a4e22785-779b-46ad-b07b-8c34939d0406'),  -- Technik
    ('max.roesner@petrofer.com', '611550d4-4b39-451d-b906-208b03010ec2'),  -- Anlagenmanagement
    ('max.roesner@petrofer.com', '280f8fdf-123b-49ba-8b19-cd5ff4eb7f79'),  -- Leitung Anlagenmanagement
    ('melanie.lemke@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('melanie.lemke@petrofer.com', '8b55cade-3b3d-4a17-8422-65c08fe085e7'),  -- Personalmanagement
    ('melanie.menzel@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('melanie.menzel@petrofer.com', '516caf26-dcd1-4b45-a79d-283723e942aa'),  -- Controlling
    ('melina.sander@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('melina.sander@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('melissa-sophie.bormke@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('melissa-sophie.bormke@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('melissa-sophie.bormke@petrofer.com', '01d40d0d-6ed9-46fc-aac3-ffa6ba8e357f'),  -- Innendienst
    ('michael.ertl@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('michael.ertl@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('michael.ertl@petrofer.com', '59c37098-5649-4b64-99e8-d7efc07e074d'),  -- Region Nord-Ost
    ('michael.nadarzinski@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('michael.nadarzinski@petrofer.com', '2900fbdf-1db3-490d-a243-afc847cb3ca2'),  -- Produktion und Logistik
    ('michael.nadarzinski@petrofer.com', 'c7ce1b6b-05fb-4305-9d96-a2e91c65f25a'),  -- Produktion
    ('michael.nickl@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('michael.nickl@petrofer.com', '547ddddd-3143-4cf1-ac90-c3951028725e'),  -- Informations- und Organisationsmanagement
    ('michael.nickl@petrofer.com', 'e7eda362-2b2a-4793-ba99-e4662d0008a0'),  -- IT
    ('michael.pruefert@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('michael.pruefert@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('michael.pruefert@petrofer.com', '4a51362a-8f43-4540-b21a-6b9fd8ec41ec'),  -- Anwendungstechnik
    ('michael.schedler@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('michael.schedler@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('michael.schedler@petrofer.com', '4773b7db-e4f9-4160-84be-2f06ee7b9937'),  -- Region Süd
    ('michael.scheibner@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('michael.scheibner@petrofer.com', '86549184-0c24-4fb8-80b4-f317515a90de'),  -- Leitung Geschäftsführung CFO
    ('miriam.schmikale@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('miriam.schmikale@petrofer.com', '547ddddd-3143-4cf1-ac90-c3951028725e'),  -- Informations- und Organisationsmanagement
    ('miriam.schmikale@petrofer.com', '61d0adc6-033c-4649-bb1b-c589616eef58'),  -- Integriertes Management System
    ('natalja.mainhardt@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('natalja.mainhardt@petrofer.com', '30444b8e-ccf1-4868-9d98-47320b03e12c'),  -- Tax management
    ('nebojsa.obradovic@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('nebojsa.obradovic@petrofer.com', 'e8982280-291a-4913-a86e-fe4a5adf5c1a'),  -- Leitung Geschäftsführung (COO) Metalworking Europe
    ('nick.markgraf@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('nick.markgraf@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('nick.markgraf@petrofer.com', '8eba657b-f161-4441-905b-67cab7e8f387'),  -- F&E 3 Hydraulik und Schmierungstechnik Entwicklung
    ('nicolas.ebel@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('nicolas.ebel@petrofer.com', '2a72c5a7-7f39-4709-b7e5-f1174331e34f'),  -- Einkauf
    ('nicolaus.dorn@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('nicolaus.dorn@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('nicolaus.dorn@petrofer.com', '019069a9-556a-4831-9ffb-76a502f47d49'),  -- F&E 1 Gießereitechnik
    ('niklas.thiel@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('niklas.thiel@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('niklas.thiel@petrofer.com', 'cb660fc0-9dce-4a9d-846b-2979beda2ee3'),  -- F&E 2 Wärmebehandlung
    ('nikola.lazic@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('nikola.lazic@petrofer.com', 'a4e22785-779b-46ad-b07b-8c34939d0406'),  -- Technik
    ('nikola.lazic@petrofer.com', 'a9819947-2e92-490c-83af-a3735f64988f'),  -- Instandhaltung
    ('nils.hammerschmidt@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('nils.hammerschmidt@petrofer.com', 'a4e22785-779b-46ad-b07b-8c34939d0406'),  -- Technik
    ('nils.hammerschmidt@petrofer.com', '611550d4-4b39-451d-b906-208b03010ec2'),  -- Anlagenmanagement
    ('ning.xu@fischerequity.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('norbert.keller@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('norbert.keller@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('norbert.keller@petrofer.com', 'b0d7510a-f0c2-4cb3-92af-5df3a82b7ac3'),  -- Global Key Account Management
    ('norman.gottschlich@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('norman.gottschlich@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('norman.gottschlich@petrofer.com', 'cb660fc0-9dce-4a9d-846b-2979beda2ee3'),  -- F&E 2 Wärmebehandlung
    ('nurcan.yapici@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('nurcan.yapici@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('nurcan.yapici@petrofer.com', 'cb660fc0-9dce-4a9d-846b-2979beda2ee3'),  -- F&E 2 Wärmebehandlung
    ('oeznur.mavigoek@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('oeznur.mavigoek@petrofer.com', '516caf26-dcd1-4b45-a79d-283723e942aa'),  -- Controlling
    ('olga.thiele@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('olga.thiele@petrofer.com', '8b55cade-3b3d-4a17-8422-65c08fe085e7'),  -- Personalmanagement
    ('oliver.oest@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('oliver.oest@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('oliver.oest@petrofer.com', '4a51362a-8f43-4540-b21a-6b9fd8ec41ec'),  -- Anwendungstechnik
    ('pascal.coupechoux@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('pascal.coupechoux@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('pascal.coupechoux@petrofer.com', '4a51362a-8f43-4540-b21a-6b9fd8ec41ec'),  -- Anwendungstechnik
    ('patrick.kutzler@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('patrick.kutzler@petrofer.com', '2900fbdf-1db3-490d-a243-afc847cb3ca2'),  -- Produktion und Logistik
    ('patrick.kutzler@petrofer.com', 'c7ce1b6b-05fb-4305-9d96-a2e91c65f25a'),  -- Produktion
    ('patrick.kutzler@petrofer.com', '93cc8469-2dee-4f64-a707-43a579d0f310'),  -- Leitung Produktion
    ('paul.geffert@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('paul.geffert@petrofer.com', '547ddddd-3143-4cf1-ac90-c3951028725e'),  -- Informations- und Organisationsmanagement
    ('paul.geffert@petrofer.com', 'e7eda362-2b2a-4793-ba99-e4662d0008a0'),  -- IT
    ('paul.labocha@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('paul.labocha@petrofer.com', 'a4e22785-779b-46ad-b07b-8c34939d0406'),  -- Technik
    ('paul.labocha@petrofer.com', 'a9819947-2e92-490c-83af-a3735f64988f'),  -- Instandhaltung
    ('petra.arndt@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('petra.arndt@petrofer.com', '3e12a594-e449-4c75-866f-0fe0b73379b1'),  -- Produktmanagement
    ('petra.halus@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('petra.halus@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('petra.halus@petrofer.com', '709907ec-7ce6-4552-b74e-ba3355c62120'),  -- Zentrale Analytik
    ('phil+testpetrofer@beyondtheloop.ai', '3e12a594-e449-4c75-866f-0fe0b73379b1'),  -- Produktmanagement
    ('phil+testpetrofer@beyondtheloop.ai', '15f7da41-c840-4fac-b403-701bc12742ad'),  -- Marketing
    ('phil+testpetrofer@beyondtheloop.ai', '8f9b6c68-5742-493e-8e3e-d5bc56bf2ac7'),  -- F&E 5 Industriereiniger und Korrosionsschutz
    ('phil+testpetrofer@beyondtheloop.ai', '416c83b7-3b6f-4cbe-8cf5-3e509bf6e9c4'),  -- Logistik
    ('phil+testpetrofer@beyondtheloop.ai', 'f92903f4-1f5f-4c8b-8720-5a1153bdfacf'),  -- Export
    ('phil+testpetrofer@beyondtheloop.ai', '2a72c5a7-7f39-4709-b7e5-f1174331e34f'),  -- Einkauf
    ('phil+testpetrofer@beyondtheloop.ai', 'b0d7510a-f0c2-4cb3-92af-5df3a82b7ac3'),  -- Global Key Account Management
    ('phil+testpetrofer@beyondtheloop.ai', '280f8fdf-123b-49ba-8b19-cd5ff4eb7f79'),  -- Leitung Anlagenmanagement
    ('phil+testpetrofer@beyondtheloop.ai', 'a4e22785-779b-46ad-b07b-8c34939d0406'),  -- Technik
    ('phil+testpetrofer@beyondtheloop.ai', 'e4a81f2b-7e38-4081-b163-1b3f7bc6db53'),  -- Geschäftsführung Strategie
    ('quentin.mayer@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('quentin.mayer@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('quentin.mayer@petrofer.com', 'f48017b8-0e09-449c-8968-2e2b510154da'),  -- F&E 4 Zerspanung und Umformung
    ('rafael.delcorralsanchez@petrofer.com', 'e4a81f2b-7e38-4081-b163-1b3f7bc6db53'),  -- Geschäftsführung Strategie
    ('rafael.delcorralsanchez@petrofer.com', 'b0757f1f-8c6d-4533-a461-2e8638c6eb52'),  -- Papierchemikalien
    ('ramon.linares@petrofer.com', 'e4a81f2b-7e38-4081-b163-1b3f7bc6db53'),  -- Geschäftsführung Strategie
    ('ramon.linares@petrofer.com', 'b0757f1f-8c6d-4533-a461-2e8638c6eb52'),  -- Papierchemikalien
    ('ramon.scheunert@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('ramon.scheunert@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('ramon.scheunert@petrofer.com', 'f92903f4-1f5f-4c8b-8720-5a1153bdfacf'),  -- Export
    ('rebecca.sauss@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('rebecca.sauss@petrofer.com', '516caf26-dcd1-4b45-a79d-283723e942aa'),  -- Controlling
    ('rene.bettels@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('rene.bettels@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('rene.bettels@petrofer.com', 'b0d7510a-f0c2-4cb3-92af-5df3a82b7ac3'),  -- Global Key Account Management
    ('rene.herzog@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('rene.herzog@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('rene.herzog@petrofer.com', '59c37098-5649-4b64-99e8-d7efc07e074d'),  -- Region Nord-Ost
    ('rene.herzog@petrofer.com', '5adc514e-11e2-4dc7-8fb0-6175fcda2d4c'),  -- Leitung Region Nord-Ost
    ('ricardo.loges@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('ricardo.loges@petrofer.com', 'a4e22785-779b-46ad-b07b-8c34939d0406'),  -- Technik
    ('ricardo.loges@petrofer.com', '611550d4-4b39-451d-b906-208b03010ec2'),  -- Anlagenmanagement
    ('rick.matthias@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('rick.matthias@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('rick.matthias@petrofer.com', '8f9b6c68-5742-493e-8e3e-d5bc56bf2ac7'),  -- F&E 5 Industriereiniger und Korrosionsschutz
    ('roberto.cagna@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('roberto.cagna@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('roberto.cagna@petrofer.com', 'a7fb09b0-b131-4c56-9776-23cc7d33716b'),  -- Region West-Mitte
    ('robin.strothotte@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('robin.strothotte@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('robin.strothotte@petrofer.com', '01d40d0d-6ed9-46fc-aac3-ffa6ba8e357f'),  -- Innendienst
    ('roger.altenburg@petrofer.com', 'e4a81f2b-7e38-4081-b163-1b3f7bc6db53'),  -- Geschäftsführung Strategie
    ('roger.altenburg@petrofer.com', 'b0757f1f-8c6d-4533-a461-2e8638c6eb52'),  -- Papierchemikalien
    ('roland.guenther@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('roland.guenther@petrofer.com', '547ddddd-3143-4cf1-ac90-c3951028725e'),  -- Informations- und Organisationsmanagement
    ('roland.guenther@petrofer.com', 'e7eda362-2b2a-4793-ba99-e4662d0008a0'),  -- IT
    ('roland.peters@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('roland.peters@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('roland.peters@petrofer.com', '019069a9-556a-4831-9ffb-76a502f47d49'),  -- F&E 1 Gießereitechnik
    ('roman.lerich@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('roman.lerich@petrofer.com', '2900fbdf-1db3-490d-a243-afc847cb3ca2'),  -- Produktion und Logistik
    ('roman.lerich@petrofer.com', '416c83b7-3b6f-4cbe-8cf5-3e509bf6e9c4'),  -- Logistik
    ('ruediger.reichhardt@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('ruediger.reichhardt@petrofer.com', '3e12a594-e449-4c75-866f-0fe0b73379b1'),  -- Produktmanagement
    ('sabine.niele@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('sabine.niele@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('sabine.niele@petrofer.com', '8f9b6c68-5742-493e-8e3e-d5bc56bf2ac7'),  -- F&E 5 Industriereiniger und Korrosionsschutz
    ('sabine.rost@petrofer.com', 'e4a81f2b-7e38-4081-b163-1b3f7bc6db53'),  -- Geschäftsführung Strategie
    ('sabine.rost@petrofer.com', 'b0757f1f-8c6d-4533-a461-2e8638c6eb52'),  -- Papierchemikalien
    ('sandra.deister@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('sandra.deister@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('sandra.deister@petrofer.com', '8f9b6c68-5742-493e-8e3e-d5bc56bf2ac7'),  -- F&E 5 Industriereiniger und Korrosionsschutz
    ('sandra.greier@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('sandra.greier@petrofer.com', '2900fbdf-1db3-490d-a243-afc847cb3ca2'),  -- Produktion und Logistik
    ('sandra.greier@petrofer.com', '416c83b7-3b6f-4cbe-8cf5-3e509bf6e9c4'),  -- Logistik
    ('sascha.petsch@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('sascha.petsch@petrofer.com', '8b55cade-3b3d-4a17-8422-65c08fe085e7'),  -- Personalmanagement
    ('scott.nicholson@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('scott.nicholson@petrofer.com', '2900fbdf-1db3-490d-a243-afc847cb3ca2'),  -- Produktion und Logistik
    ('scott.nicholson@petrofer.com', 'c7ce1b6b-05fb-4305-9d96-a2e91c65f25a'),  -- Produktion
    ('sebastian.siemens@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('sebastian.siemens@petrofer.com', '3e12a594-e449-4c75-866f-0fe0b73379b1'),  -- Produktmanagement
    ('sibel.elmas@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('sibel.elmas@petrofer.com', '2a72c5a7-7f39-4709-b7e5-f1174331e34f'),  -- Einkauf
    ('sibel.elmas@petrofer.com', '1c511479-d1f2-4ba7-9c45-0eef0e25acba'),  -- Leitung Einkauf
    ('silke.bansemer@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('silke.bansemer@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('silke.bansemer@petrofer.com', '709907ec-7ce6-4552-b74e-ba3355c62120'),  -- Zentrale Analytik
    ('silvio.kraack@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('silvio.kraack@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('silvio.kraack@petrofer.com', '4a51362a-8f43-4540-b21a-6b9fd8ec41ec'),  -- Anwendungstechnik
    ('simon.scheunert@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('simon.scheunert@petrofer.com', '2900fbdf-1db3-490d-a243-afc847cb3ca2'),  -- Produktion und Logistik
    ('simon.scheunert@petrofer.com', 'c7ce1b6b-05fb-4305-9d96-a2e91c65f25a'),  -- Produktion
    ('simone.fischer@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('sonja.zelazo@petrofer.com', 'e4a81f2b-7e38-4081-b163-1b3f7bc6db53'),  -- Geschäftsführung Strategie
    ('sonja.zelazo@petrofer.com', 'b0757f1f-8c6d-4533-a461-2e8638c6eb52'),  -- Papierchemikalien
    ('stefan.menzel@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('stefan.menzel@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('stefan.menzel@petrofer.com', '8f9b6c68-5742-493e-8e3e-d5bc56bf2ac7'),  -- F&E 5 Industriereiniger und Korrosionsschutz
    ('stefan.schettiger@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('stefan.schettiger@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('stefan.schettiger@petrofer.com', 'f48017b8-0e09-449c-8968-2e2b510154da'),  -- F&E 4 Zerspanung und Umformung
    ('stefan.schindler@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('stefan.schindler@petrofer.com', '547ddddd-3143-4cf1-ac90-c3951028725e'),  -- Informations- und Organisationsmanagement
    ('stefan.schindler@petrofer.com', '61d0adc6-033c-4649-bb1b-c589616eef58'),  -- Integriertes Management System
    ('stefanie.gefroerer@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('stefanie.gefroerer@petrofer.com', '30e5d414-3ca8-4dfb-8201-a8a562e3a98c'),  -- Finanzen
    ('steffen.henkel@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('steffen.henkel@petrofer.com', '3e12a594-e449-4c75-866f-0fe0b73379b1'),  -- Produktmanagement
    ('stephan.eberding@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('stephan.woiwode@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('stephan.woiwode@petrofer.com', '3e12a594-e449-4c75-866f-0fe0b73379b1'),  -- Produktmanagement
    ('susanne.finke@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('susanne.finke@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('susanne.finke@petrofer.com', '4a51362a-8f43-4540-b21a-6b9fd8ec41ec'),  -- Anwendungstechnik
    ('sven.ossenkop@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('sven.ossenkop@petrofer.com', '2900fbdf-1db3-490d-a243-afc847cb3ca2'),  -- Produktion und Logistik
    ('sven.ossenkop@petrofer.com', '416c83b7-3b6f-4cbe-8cf5-3e509bf6e9c4'),  -- Logistik
    ('tabea.soencksen@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('tabea.soencksen@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('tabea.soencksen@petrofer.com', 'f4e83e06-a218-45c7-8a86-575c76198915'),  -- Sicherheitsdatentechnik
    ('tanja.kuhl@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('tanja.kuhl@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('tanja.kuhl@petrofer.com', '01d40d0d-6ed9-46fc-aac3-ffa6ba8e357f'),  -- Innendienst
    ('tanja.probst@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('tanja.probst@petrofer.com', '30e5d414-3ca8-4dfb-8201-a8a562e3a98c'),  -- Finanzen
    ('tanja.probst@petrofer.com', '5fc2c0a2-d5a2-4bf2-af43-0afa5520468b'),  -- Leitung Finanzen
    ('thomas.brandenburger@petrofer.com', 'e4a81f2b-7e38-4081-b163-1b3f7bc6db53'),  -- Geschäftsführung Strategie
    ('thomas.brandenburger@petrofer.com', 'b0757f1f-8c6d-4533-a461-2e8638c6eb52'),  -- Papierchemikalien
    ('thomas.sobotta@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('thomas.sobotta@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('thomas.sobotta@petrofer.com', '8eba657b-f161-4441-905b-67cab7e8f387'),  -- F&E 3 Hydraulik und Schmierungstechnik Entwicklung
    ('thomas.sobotta@petrofer.com', 'c421cdda-38c1-4cfd-8b58-82a68982abff'),  -- Leitung F&E 3 Hydraulik und Schmierungstechnik Entwicklung
    ('thorsten.beitz@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('thorsten.beitz@petrofer.com', '3e12a594-e449-4c75-866f-0fe0b73379b1'),  -- Produktmanagement
    ('tim.kurbjoweit@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('tim.kurbjoweit@petrofer.com', '2900fbdf-1db3-490d-a243-afc847cb3ca2'),  -- Produktion und Logistik
    ('tim.kurbjoweit@petrofer.com', 'c7ce1b6b-05fb-4305-9d96-a2e91c65f25a'),  -- Produktion
    ('timo.haefele@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('timo.haefele@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('timo.haefele@petrofer.com', '4773b7db-e4f9-4160-84be-2f06ee7b9937'),  -- Region Süd
    ('timo.haefele@petrofer.com', '66a860cb-b0a6-4a3e-9c32-bcc3701ca0e1'),  -- Leitung Region Süd
    ('timo.voegtel@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('timo.voegtel@petrofer.com', '547ddddd-3143-4cf1-ac90-c3951028725e'),  -- Informations- und Organisationsmanagement
    ('timo.voegtel@petrofer.com', 'e7eda362-2b2a-4793-ba99-e4662d0008a0'),  -- IT
    ('tobias.arnold@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('tobias.arnold@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('tobias.arnold@petrofer.com', '709907ec-7ce6-4552-b74e-ba3355c62120'),  -- Zentrale Analytik
    ('tobias.arnold@petrofer.com', 'e6e38901-fe70-489a-ada2-b61dfeb636ed'),  -- Leitung Zentrale Analytik
    ('ulf.kussroll@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('ulf.kussroll@petrofer.com', '2a72c5a7-7f39-4709-b7e5-f1174331e34f'),  -- Einkauf
    ('ulrike.stuempel@petrofer.com', 'ca8a0340-baac-4da5-90ea-b96cf8e820a0'),  -- Geschäftsführung CFO
    ('ulrike.stuempel@petrofer.com', '547ddddd-3143-4cf1-ac90-c3951028725e'),  -- Informations- und Organisationsmanagement
    ('ulrike.stuempel@petrofer.com', '61d0adc6-033c-4649-bb1b-c589616eef58'),  -- Integriertes Management System
    ('vefa.altinkilic@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('vefa.altinkilic@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('vefa.altinkilic@petrofer.com', '01d40d0d-6ed9-46fc-aac3-ffa6ba8e357f'),  -- Innendienst
    ('veronique.meyerhoff@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('veronique.meyerhoff@petrofer.com', 'd5751d2a-fbe1-48ad-be87-f28dde85e5ff'),  -- Forschung und Entwicklung
    ('veronique.meyerhoff@petrofer.com', '709907ec-7ce6-4552-b74e-ba3355c62120'),  -- Zentrale Analytik
    ('volker.veit@petrofer.com', 'a40025e4-179e-49a7-821a-0d0249119748'),  -- Geschäftsführung CEO
    ('volker.veit@petrofer.com', '2900fbdf-1db3-490d-a243-afc847cb3ca2'),  -- Produktion und Logistik
    ('volker.veit@petrofer.com', 'c7ce1b6b-05fb-4305-9d96-a2e91c65f25a'),  -- Produktion
    ('yahya.elci@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('yahya.elci@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('yahya.elci@petrofer.com', '4a51362a-8f43-4540-b21a-6b9fd8ec41ec'),  -- Anwendungstechnik
    ('yesim.atayer@petrofer.com', 'bf0cf044-8ab8-4e12-a758-88518b95d694'),  -- Geschäftsführung (COO) Metalworking Europe
    ('yesim.atayer@petrofer.com', '03012285-b5d5-46a3-ac70-559676c24d7c'),  -- Vertrieb Metalworking Europe
    ('yesim.atayer@petrofer.com', '01d40d0d-6ed9-46fc-aac3-ffa6ba8e357f'),  -- Innendienst
    ('yesim.atayer@petrofer.com', '2ed25d80-606d-42e0-bff5-d890cbb4e082');  -- Leitung Innendienst

-- --- DRY-RUN SUMMARY (safe) --------------------------------------------
SELECT
    (SELECT count(*) FROM "user" WHERE company_id = '383e3338-9883-4b3e-8dd6-d32f9a58339f') AS total_petrofer_users_in_db,
    count(DISTINCT u.id)       AS users_matched_by_mapping,
    count(*)                   AS raw_pair_matches,
    count(DISTINCT m.group_id) AS distinct_groups_touched
FROM _petrofer_mapping m
JOIN "user" u
  ON lower(trim(u.email)) = m.email
 AND u.company_id = '383e3338-9883-4b3e-8dd6-d32f9a58339f';

-- --- ACTUAL UPDATE -----------------------------------------------------
WITH new_memberships AS (
    SELECT m.group_id, jsonb_agg(to_jsonb(u.id)) AS to_add
    FROM _petrofer_mapping m
    JOIN "user" u
      ON lower(trim(u.email)) = m.email
     AND u.company_id = '383e3338-9883-4b3e-8dd6-d32f9a58339f'
    JOIN "group" g
      ON g.id = m.group_id
     AND g.company_id = '383e3338-9883-4b3e-8dd6-d32f9a58339f'
    WHERE NOT (COALESCE(g.user_ids::jsonb, '[]'::jsonb) @> to_jsonb(u.id))
    GROUP BY m.group_id
)
UPDATE "group" g
SET user_ids   = (COALESCE(g.user_ids::jsonb, '[]'::jsonb) || nm.to_add)::json,
    updated_at = extract(epoch from now())::bigint
FROM new_memberships nm
WHERE g.id = nm.group_id
  AND g.company_id = '383e3338-9883-4b3e-8dd6-d32f9a58339f';

-- --- POST-UPDATE VERIFY (safe) -----------------------------------------
SELECT g.id, g.name, jsonb_array_length(g.user_ids::jsonb) AS user_count
FROM "group" g
WHERE g.company_id = '383e3338-9883-4b3e-8dd6-d32f9a58339f'
  AND g.id IN (SELECT DISTINCT group_id FROM _petrofer_mapping)
ORDER BY user_count DESC
LIMIT 20;

-- COMMIT;   -- <-- uncomment when the numbers look correct
-- ROLLBACK; -- <-- or this to undo everything
