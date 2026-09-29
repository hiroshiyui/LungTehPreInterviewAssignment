### HR Cost

A Frappe app that records employees' working hours and reports the total HR
cost per day.

| DocType / Report | Purpose |
| --- | --- |
| **Employee** | `Employee Name`, `Hourly Rate` (must be > 0), and an **Hourly Rate History** table (child DocType *Employee Hourly Rate*: `Valid From`, `Hourly Rate`). Named `EMP-00001`, … and shown by name in links. |
| **Work Record** | `Employee` (link) + fetched `Employee Name`, `Date`, `Hours Worked`. On save it takes the rate **valid on its date** from the history and stores `Cost = Hours Worked × Hourly Rate`. |
| **Daily HR Cost** (Script Report) | One row per day: number of employees, hours worked, total HR cost. Filters: date range (defaults to the current month) and an optional employee. Also shows a bar chart and period totals (total cost, total hours, days with work, average cost per day). |

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

Upgrading an existing site: `bench migrate` runs the patch
`hr_cost.patches.v0_1.seed_hourly_rate_history`, which gives each existing
Employee a base rate equal to its current `Hourly Rate`. Existing Work
Records keep their stored cost until that employee's history is edited.

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
