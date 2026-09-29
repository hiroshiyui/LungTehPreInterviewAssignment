### HR Cost

A Frappe app that records employees' working hours and reports the total HR
cost per day and per month.

| DocType / Report | Purpose |
| --- | --- |
| **Employee** | `Employee Name`, `Nationality`, **Names in Other Writing Systems** (child DocType *Employee Other Name*: `Writing System`, `Name`), `Date of Joining`, `Relieving Date`, the **Work Permit** (`Number`, `Expiry`), and pay per the employment contract: `Pay Basis` (Hourly or Monthly) with `Hourly Rate` or `Monthly Salary` (must be > 0), kept as a **Pay History** table (child DocType *Employee Hourly Rate*: `Valid From`, `Pay Basis`, `Hourly Rate`, `Monthly Salary`), plotted as a line under the table. Named `EMP-00001`, … and shown by name in links. |
| **Work Record** | `Employee` (link) + fetched `Employee Name`, `Date`, `Hours Worked`. On save it takes the rate **valid on its date** from the Pay History and stores `Cost = Hours Worked × Hourly Rate`: 0 under monthly pay, whose salary covers the hours. |
| **Daily HR Cost** (Script Report) | One row per day: number of employees, hours worked, hourly wages, salaries, total HR cost. Filters: date range (defaults to the current month), and an optional employee or nationality. Period totals: total cost, total hours, days with work, average cost per day. The "Chart" filter picks HR Cost, Hours Worked or Employees at Work per day. "Show days without work" adds zero rows for the chart's time axis. |
| **Monthly HR Cost** (Script Report) | One row per employee, one column per month in the range (months without work show 0), plus the employee's total hours and cost, and a total row. Filters: date range (defaults to the current year), and an optional employee or nationality. Totals: total cost, total hours, employees, average cost per month with work, and the latest month with work against the month before it (red when cost rose). The "Chart" filter picks Cost by Employee (stacked bars per month), Cost Share (donut) or Effective Hourly Rate (cost ÷ hours per month; it moves with raises and with who did the work). |
| **HR Cost** (Workspace) | `/desk/hr-cost`, HR Manager only. Number cards: HR cost this month, hours worked this month, HR cost this year. Charts: cost by employee, daily cost this month, cost share, effective hourly rate. Every card and chart reads one of the two reports (Report-type Number Cards and Dashboard Charts), so it inherits their permission checks. |

Business rules:

* `Hours Worked` must be > 0, and one employee cannot have more than 24 hours
  on the same date across all their work records. The Employee row is locked
  during the check, so simultaneous saves can't slip past it together.
* A Work Record can't be dated in the future.
* **Hourly or monthly pay**, as the employment contract says (Taiwan's labour
  law allows either). A monthly salary accrues at salary ÷ 30 per calendar
  day, weekends included, from the Date of Joining to the Relieving Date and
  never beyond today; the reports add it to the hourly wages. A monthly-paid
  worker's Work Records log hours only (rate and cost 0). Pay terms can change
  on a date, e.g. hourly until the 15th, monthly from then on.
* Staff come from many countries. `Employee Name` is the one name shown
  everywhere; the same person's name in other writing systems (the
  passport's Latin spelling, Chinese, Thai, Vietnamese, …) is kept alongside.
  PDFs print names in any of these scripts (the server has Noto fonts).
* Work permits: saving an Employee warns when the permit expires within 30
  days or has expired (while employed), and so does the form's header. A
  Work Record dated after the expiry is saved with a warning.
* A Work Record must fall within the employee's employment (Date of Joining
  to Relieving Date), and those dates can't be moved past recorded work.
* **Pay terms are dated.** Each row of an employee's Hourly Rate History applies
  from its `Valid From` date; the row with an empty `Valid From` is the base
  rate, which applies before any dated change. A Work Record is costed at the
  rate valid on its date. A raise (a new dated row) therefore never changes
  earlier work, and work entered late is still costed at the rate of its day.
* A new Employee's `Hourly Rate` becomes its base rate. Afterwards the field is
  read-only and shows the latest rate: change rates by adding a history row.
* Editing the history (for example, fixing a mistyped rate) re-costs that
  employee's affected Work Records. An edit that would leave a record with no
  valid rate is refused.
* Work Record is indexed on `date` (the report) and on `(employee, date)`
  (the 24 h check).
* Work Record copies the employee's name (the assignment's "Employee Name").
  Renaming the Employee updates the copies.
* Two employees may share a name; saving the second one warns. Pickers show
  the ID under each name.
* Work Records can be imported (Data Import). Each row is inserted like a
  form save: the server costs it (an imported Cost column is ignored) and the
  24 h cap applies. Frappe's Data Import tool itself is System-Manager-only.
* In the Daily HR Cost report, each date links to that day's Work Records.
* Both reports have a **Download PDF** button: the current view as an A4 file
  (`report/pdf.py`, template `report/report_pdf.html`), named after the report
  and period (and the employee's ID when filtered). It needs `wkhtmltopdf`
  on the server, plus fonts for every script employees' names use (the
  `base` role installs Noto: `fonts-noto-cjk` and `fonts-noto-core`). Only the reports' roles
  can download it, and it runs the reports' own permission-aware queries.

Roles and pay confidentiality:

| Role | Employees | Work Records | Pay (rates, rate history, costs) | Reports |
| --- | --- | --- | --- | --- |
| **HR Manager** | create, edit, delete | create, edit, delete | read (and edit rates) | yes |
| **HR User** | read (names only) | create, edit, delete | hidden | no |
| **System Manager** | edit, delete | create, edit, delete | hidden | no |

* Pay fields are at **permlevel 1**. Frappe hides them from users without
  access to that level: in forms, lists, the REST API and the rate preview.
  A value such a user submits for them is discarded; the server still costs
  every record.
* The reports honour **User Permissions**: an HR Manager restricted to some
  employees sees only their costs.
* A System Manager administers the site but doesn't see pay, so it can't
  create employees either (a new employee needs a rate). Give a user the HR
  Manager role to manage employees and rates (Administrator has every role).
* The roles ship as fixtures (`hr_cost/fixtures/role.json`), created by
  `install-app` and `migrate`.

Upgrading an existing site: `bench migrate` runs the patch
`hr_cost.patches.v0_1.seed_hourly_rate_history`, which gives each existing
Employee a base rate equal to its current `Hourly Rate`. Existing Work
Records keep their stored cost until that employee's history is edited.
The patch `hr_cost.patches.v0_2.set_pay_basis_and_joining_dates` then marks
everyone paid so far as Hourly, and sets each Date of Joining to the
employee's first Work Record (or the day they were created). No cost changes.
The same `migrate` adds the HR roles; System Manager users then lose access
to pay and the reports until they're given the HR Manager role.

Sample data: `bench --site <site> execute hr_cost.demo.create_demo_data`
(idempotent). It also creates two demo users, `hr.manager@example.com` (HR
Manager) and `hr.user@example.com` (HR User), both with the password `demo`.
Load it on a local tutorial site only.

Tests: `bench --site <site> run-tests --app hr_cost`

### Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO
bench --site <site> install-app hr_cost
```

> Frappe core has no `Employee` DocType, but ERPNext/HRMS do. Do not install
> this app on a site that also has one of those.

#### License

mit
