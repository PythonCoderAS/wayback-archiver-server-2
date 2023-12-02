import { Button, Typography, Box } from "@mui/material";
import { useContext } from "react";
import { useNavigate } from "react-router-dom";
import { SetTitleContext } from "../AppFrame";

export default function Error404() {
  const nav = useNavigate();
  const setTitle = useContext(SetTitleContext);

  setTitle("404 Not Found");

  return (
    <Box
      display="flex"
      justifyContent="center"
      alignContent="center"
      flexDirection="column"
    >
      <div>
        <Typography variant="body1" fontSize="200%">
          The page you requested does not exist.
        </Typography>
      </div>
      <div>
        <Button variant="contained" onClick={() => nav(-1)}>
          Go back
        </Button>
      </div>
    </Box>
  );
}
