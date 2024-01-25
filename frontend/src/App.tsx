import { RouterProvider, createBrowserRouter } from "react-router-dom";

import Sidebar from "./AppFrame";
import Error404 from "./routes/404";
import Home from "./routes/Home";
import ViewBatch from "./routes/batch/ViewBatch";
import ViewJobs from "./routes/job/ViewJobs";

export default function App() {
  const router = createBrowserRouter(
    [
      {
        path: "*",
        Component: Sidebar,
        children: [
          {
            index: true,
            Component: Home,
          },
          {
            path: "job",
            Component: ViewJobs,
          },
          {
            path: "batch",
          },
          {
            path: "batch/:batchId",
            Component: ViewBatch,
          },
          { path: "*", Component: Error404 },
        ],
      },
    ],
    {
      basename: "/app/",
    },
  );

  return <RouterProvider router={router} />;
}
