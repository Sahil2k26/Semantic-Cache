# Frontend Changes Required for Backend Connection

Currently, the dashboard frontend uses **dummy data** for demonstration purposes. 
To connect the frontend to the actual backend API endpoints, you need to navigate to the following files and uncomment the actual API connection logic inside their respective `useEffect` hooks, and remove or comment out the dummy data logic.

### 1. Overview Page (`src/app/page.tsx`)
*   **What to change**: 
    *   Uncomment the block inside `useEffect` under `// TODO: Uncomment when connecting to actual backend`. This block handles fetching `/insights/top-queries`, `/metrics/historical`, and setting up the WebSocket connection to `ws://localhost:8000/ws/realtime`.
    *   Comment out or remove the section under `// DUMMY DATA LOGIC`.

### 2. Query Patterns Page (`src/app/patterns/page.tsx`)
*   **What to change**:
    *   Uncomment the fetch calls inside `useEffect` targeting `/insights/patterns` and `/insights/recent`.
    *   Comment out or remove the `setPatterns` and `setRecentQueries` calls with hardcoded dummy data.

### 3. Semantic Clusters Page (`src/app/clusters/page.tsx`)
*   **What to change**:
    *   Uncomment the fetch call inside `useEffect` targeting `/insights/clusters`.
    *   Comment out or remove the `for` loop that generates random coordinates for the `dummyClusters`.

### 4. Cost Analytics Page (`src/app/cost/page.tsx`)
*   **What to change**:
    *   Uncomment the fetch call inside `useEffect` targeting `/metrics/cost`.
    *   Comment out or remove the `setCostData` and `setTotalSaved` calls that use dummy data values.
