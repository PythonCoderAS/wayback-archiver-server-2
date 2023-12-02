import { RouterProvider, createBrowserRouter } from "react-router-dom";
import Sidebar from "./AppFrame";
import Home from "./routes/Home";
import ViewBatch from "./routes/batch/ViewBatch";
import Error404 from "./routes/404";

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
            path: "batches",
          },
          {
            path: "batches/:batchId",
            Component: ViewBatch,
          },
          { path: "*", Component: Error404 },
        ],
      },
    ],
    {
      basename: "/app/",
    }
  );

  return <RouterProvider router={router} />;
}
