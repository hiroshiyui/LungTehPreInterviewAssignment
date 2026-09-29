### HR Cost

A Frappe app that records employees' working hours and reports the total HR
cost per day and per month.

| DocType / Report | Purpose |
| --- | --- |
| **Employee** | `Employee Name`, `Hourly Rate` (must be > 0), and an **Hourly Rate History** table (child DocType *Employee Hourly Rate*: `Valid From`, `Hourly Rate`), plotted as a line under the table. Named `EMP-00001`, … and shown by name in links. |
| **Work Record** | `Employee` (link) + fetched `Employee Name`, `Date`, `Hours Worked`. On save it takes the rate **valid on its date** from the history and stores `Cost = Hours Worked × Hourly Rate`. |
| **Daily HR Cost** (Script Report) | One row per day: number of employees, hours worked, total HR cost. Filters: date range (defaults to the current month) and an optional employee. Period totals: total cost, total hours, days with work, average cost per day. The "Chart" filter picks HR Cost, Hours Worked or Employees at Work per day. "Show days without work" adds zero rows for the chart's time axis. |
| **Monthly HR Cost** (Script Report) | One row per employee, one column per month in the range (months without work show 0), plus the employee's total hours and cost, and a total row. Filters: date range (defaults to the current year) and an optional employee. Totals: total cost, total hours, employees, average cost per month with work, and the latest month with work against the month before it (red when cost rose). The "Chart" filter picks Cost by Employee (stacked bars per month), Cost Share (donut) or Effective Hourly Rate (cost ÷ hours per month; it moves with raises and with who did the work). |
| **HR Cost** (Workspace) | `/desk/hr-cost`, HR Manager only. Number cards: HR cost this month, hours worked this month, HR cost this year. Charts: cost by employee, daily cost this month, cost share, effective hourly rate. Every card and chart reads one of the two reports (Report-type Number Cards and Dashboard Charts), so it inherits their permission checks. |

Business rules:

* `Hours Worked` must be > 0, and one employee cannot have more than 24 hours
  on the same date across all their work records. The Employee row is locked
  during the check, so simultaneous saves can't slip past it together.
* A Work Record can't be dated in the future.
* **Rates are dated.** Each row of an employee's Hourly Rate History applies
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
The same `migrate` adds the HR roles; System Manager users then lose access
to pay and the reports until they're given the HR Manager role.

Sample data: `bench --site <site> execute hr_cost.demo.create_demo_data`
(idempotent).

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
