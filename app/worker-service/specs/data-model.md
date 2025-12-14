# Worker Service - Data Model

The Worker Service does not have its own dedicated database. Instead, it interacts with the central **Database** of the application to update the status of logs and store the generated fixes. The data models it uses are the same as those defined in the **Backend API**'s data model.

Please refer to the [`app/backend-api/specs/data-model.md`](app/backend-api/specs/data-model.md) file for the definitions of the following models:

-   **Log**
-   **Fix**