import { Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { GET, type JobMaybe } from "../api/api";

export default function Home() {
  const [loadCount, setLoadCount] = useState(0);
  const [currentJob, setCurrentJob] = useState<JobMaybe>(null);

  useEffect(() => {
    GET("/current_job")
      .then(({ data }) => {
        setCurrentJob(data!.job);
      })
      .finally(() => {
        setTimeout(() => setLoadCount(loadCount + 1), 1000);
      });
  }, [loadCount]);

  return (
    <Typography>
      <h1>Wayback Archiver Server Data Viewer</h1>
      <p>
        This tool allows viewing the data in the server in a simple and
        non-painful way. Click on some of the links in the sidebar in order to
        go to the resource you are looking for.
      </p>
      <h2>Current Job</h2>
      {currentJob !== null ? (
        <p>Current Job: GET {currentJob.url}</p>
      ) : (
        <p>No current job running</p>
      )}
    </Typography>
  );
}
