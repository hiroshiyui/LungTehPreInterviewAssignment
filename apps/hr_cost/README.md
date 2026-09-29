### HR Cost

A Frappe app that records employees' working hours and reports the total HR
cost per day.

| DocType / Report | Purpose |
| --- | --- |
| **Employee** | `Employee Name`, `Hourly Rate` (must be > 0). Named `EMP-00001`, … and shown by name in links. |
| **Work Record** | `Employee` (link) + fetched `Employee Name`, `Date`, `Hours Worked`. On save it copies the employee's current `Hourly Rate` and stores `Cost = Hours Worked × Hourly Rate`. |
| **Daily HR Cost** (Script Report) | One row per day: number of employees, hours worked, total HR cost. Filters: date range (defaults to the current month) and an optional employee. Also shows a bar chart and period totals (total cost, total hours, days with work, average cost per day). |

Business rules:

* `Hours Worked` must be > 0, and one employee cannot have more than 24 hours
  on the same date across all their work records.
* The hourly rate is copied onto each Work Record when it is created (or
  moved to another employee). A later raise therefore does not change the
  cost of work already recorded.

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
