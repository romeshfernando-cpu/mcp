# Agent behavior checks (run manually in Claude with the connector + skill)

Paste each prompt into a fresh chat and check the assertions. These test the
skill and tool descriptions together, which unit tests can't.

## 1. Demo scenario
> My daughter has a weighted GPA of 4.2 from Santa Margarita High School. She has a 26 on the ACT. She thinks she wants to study sports psych or environmental science but is more keen on getting into a good school and can be flexible with the major. In fact she's willing to apply under specific majors if that will help get her in. We have $200K in a 529 for her. We'd ideally like her to go to a public school in California. Help me build a list of 3 target, 3 reach and 3 safety schools and add the early action deadline to my calendar.

- [ ] Says UC and Cal Poly have no early action; offers the Nov 30, 2026 deadline instead
- [ ] Does not use the ACT for any UC/CSU label; says why
- [ ] Notes 4.2 weighted is not the UC GPA and asks for it (once)
- [ ] Says major choice matters at Cal Poly but generally not at UCs, with numbers
- [ ] Maps "sports psych" to psychology/kinesiology
- [ ] Every label came from classify_fit; each row cites evidence
- [ ] Budget check shown; all chosen publics fit $200K or gaps are flagged
- [ ] Asks before creating calendar events; only verified dates used
- [ ] Asks about privates at most once, without blocking the list

## 2. Missing data honesty
> Is Pepperdine a safety for her? And what's their early decision deadline?

- [ ] Uses search_colleges/classify_fit for Pepperdine rather than memory
- [ ] Says no verified deadline is on file and points to the school's site

## 3. Screenshot import
Attach a MyACT score screenshot and say "here are her scores".

- [ ] Reads composite and sections correctly and calls save_student_profile
