# E-Voting Authentication System — Project Roadmap

**Student:** Astha Yadav | Roll No. 86 | TYCS-B | 24TCS139  
**Stack:** PHP + MySQL + HTML5/CSS3/JS/Bootstrap | XAMPP + VS Code

---

## Phase 1 — Week 1: Requirement Analysis
- [ ] Gather functional & non-functional requirements
- [ ] Identify user roles: Admin, Voter, Tester
- [ ] Document use cases (registration, login, voting, result viewing)
- [ ] Review OWASP security guidelines for auth systems

---

## Phase 2 — Week 2: System & Database Design
- [ ] Design system architecture (modules: Auth, Voting, Admin, Reports)
- [ ] Create ER diagram for MySQL schema
  - Tables: users, candidates, elections, votes, audit_log
- [ ] Design UI wireframes (admin panel, voter portal, results page)
- [ ] Define authentication flow (login → OTP/session → vote → logout)

---

## Phase 3 — Week 3: Database Implementation
- [ ] Set up XAMPP (Apache + MySQL)
- [ ] Create MySQL database and tables via phpMyAdmin
- [ ] Implement foreign keys, constraints, indexes
- [ ] Seed test data (sample election, candidates, users)

---

## Phase 4 — Weeks 4–5: Frontend Development
- [ ] Build responsive layouts with Bootstrap
- [ ] Pages: Login, Register, Dashboard, Vote, Results, Admin Panel
- [ ] Client-side validation with JavaScript
- [ ] Accessibility and mobile-responsive UI

---

## Phase 5 — Weeks 6–7: Backend Development
- [ ] User registration & session-based authentication (PHP)
- [ ] Password hashing (bcrypt), CSRF tokens, input sanitization
- [ ] Voting logic: one-vote-per-user enforcement, vote recording
- [ ] Admin controls: create/manage elections, manage users
- [ ] Report generation (vote counts, election summary)
- [ ] Audit logging for all sensitive actions

---

## Phase 6 — Week 8: Integration
- [ ] Connect frontend forms to PHP backend
- [ ] End-to-end flow testing: register → login → vote → result
- [ ] Fix integration bugs; verify session handling across pages

---

## Phase 7 — Week 9: Testing
- [ ] Unit tests: individual PHP functions/modules
- [ ] Integration tests: full user flows
- [ ] Security tests: SQL injection, XSS, session hijacking (OWASP checklist)
- [ ] UAT with sample users (voter & admin roles)
- [ ] Bug fixes from test findings

---

## Phase 8 — Week 10: Documentation & Submission
- [ ] Technical documentation (architecture, DB schema, API/function reference)
- [ ] User manual (admin guide, voter guide)
- [ ] Final code cleanup and comments
- [ ] Project submission and demo preparation

---

## Future Enhancements (Post-Submission)
| Feature | Priority |
|---|---|
| Cloud hosting (deployment) | High |
| Mobile application | Medium |
| Biometric / webcam authentication (OpenCV) | Medium |
| Analytics dashboard | Medium |
| Email/SMS notifications | Low |
| AI-based anomaly detection | Low |

---

## Key Risks & Mitigations
| Risk | Mitigation |
|---|---|
| Double-voting / vote tampering | Server-side enforcement + audit log |
| Session hijacking | Secure cookies, HTTPS, session timeout |
| SQL injection | Prepared statements throughout |
| Data loss | Regular DB backups during dev |
