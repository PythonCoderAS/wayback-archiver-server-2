import {
  Box,
  Drawer,
  List,
  ListItemButton,
  ListItemText,
  Paper,
  Typography,
} from "@mui/material";
import React from "react";
import {
  Outlet,
  Link as RouterLink,
  LinkProps as RouterLinkProps,
  useLocation,
} from "react-router-dom";

interface ListItemLinkProps {
  children: string;
  to: string;
}

const Link = React.forwardRef<HTMLAnchorElement, RouterLinkProps>(function Link(
  itemProps,
  ref
) {
  return <RouterLink ref={ref} {...itemProps} role={undefined} />;
});

export function ListItemLink(props: ListItemLinkProps) {
  const { children, to } = props;
  const currentPath = useLocation().pathname;

  const child = (
    <ListItemButton component={Link} to={to}>
      <ListItemText primary={children} />
    </ListItemButton>
  );

  return (
    <li>
      {currentPath === to ? (
        <Paper square sx={{ backgroundColor: "#DDDDDD" }} elevation={1}>
          {child}
        </Paper>
      ) : (
        child
      )}
    </li>
  );
}

function Sidebar() {
  return (
    <Box component="aside" sx={{ width: { sm: "10%" }, flexShrink: { sm: 0 } }}>
      <Drawer
        variant="permanent"
        anchor="left"
        sx={{ "& .MuiDrawer-paper": { boxSizing: "border-box", width: "10%" } }}
      >
        <Paper elevation={0} square>
          <List>
            <ListItemLink to="/">Home</ListItemLink>
          </List>
        </Paper>
      </Drawer>
    </Box>
  );
}

export const SetTitleContext = React.createContext<
  (newTitle: string) => unknown
>(() => {});

export default function AppFrameOutlet() {
  const [title, setTitle] = React.useState("");

  return (
    <div>
      <Box sx={{ display: "flex" }}>
        <Sidebar />
        <Box component="main" sx={{ flexGrow: 1, p: 3, width: { sm: "90%" } }}>
        <Box sx={{ width: { sm: "100%" }, px: 3, pb: 1.5, textAlign: "center", borderBottom: "1px solid black" }}>
        <Box>
          <Typography variant="h1" sx={{fontSize: "200%"}}>
            {title} {title ?? "-"} Wayback Archiver Server Data Viewer
          </Typography>
        </Box>
      </Box>
          <SetTitleContext.Provider value={setTitle}>
            <Outlet />
          </SetTitleContext.Provider>
        </Box>
      </Box>
    </div>
  );
}
