import { RouterProvider, createBrowserRouter } from "react-router-dom";
import Sidebar from "./AppFrame";
import Home from "./routes/Home";

export default function App() {
  const router = createBrowserRouter([
    {
      path: "*",
      Component: Sidebar,
      children: [
        {
          index: true,
          Component: Home,
        },
      ]
    }
  ], {
    basename: "/app/"
  });

  return <RouterProvider router={router} />;
}
