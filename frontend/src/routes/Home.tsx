import {
  Box,
  LinearProgress,
  Link as MuiLink,
  Paper,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  createTheme,
} from "@mui/material";
import React, { useContext, useEffect, useState } from "react";
import { GET, Stats, type JobMaybe } from "../api/api";
import BatchChip from "../misc/BatchChip";
import { SetTitleContext } from "../AppFrame";
import InlineSkeletonDisplay from "../misc/InlineSkeletonDisplay";
import inlineSkeleton from "../misc/inlineSkeleton";

const theme = createTheme();

function JobBanner({
  job,
  startTime,
  count = null,
}: {
  job: JobMaybe;
  startTime: Date;
  count?: number | null;
}) {
  let possibleTimeStr: string | null = null;
  let color = theme.palette.primary;
  if (count !== null) {
    if (job) {
      if (job.delayed_until) {
        color = theme.palette.warning;
        possibleTimeStr = job.delayed_until;
      } else if (job.failed) {
        color = theme.palette.error;
        possibleTimeStr = job.failed;
      } else {
        color = theme.palette.success;
        possibleTimeStr = job.completed;
      }
    }
  } else if (job === null) {
    color = theme.palette.secondary;
  }
  const finishedTime: Date | null = possibleTimeStr
    ? new Date(possibleTimeStr)
    : count
    ? new Date(startTime.getTime() + count * 1000)
    : null;
  const finishedTimeArchiveFormat: string | null = finishedTime
    ? finishedTime.toISOString().replaceAll(/[^\d]/g, "").substring(0, 14)
    : null;

  let statSection: React.ReactElement | null = null;
  let infoSection: React.ReactElement | null = null;
  if (color === theme.palette.success) {
    const actionDuration = finishedTime!.getTime() - (job?.created_at ? new Date(job.created_at) : startTime).getTime();
    // Convert actionDuration to seconds and keep the 100ths place
    const actionDurationSeconds = Math.round(actionDuration / 100) / 10;
    statSection = (
      <span>
        Completed in {actionDurationSeconds} seconds
      </span>
    )
    infoSection = (
      <span>
        <MuiLink
          href={`https://web.archive.org/web/${finishedTimeArchiveFormat}/${
            job!.url
          }`}
          color="inherit"
          underline="hover"
          target="_blank"
          rel="noreferrer"
        >
          View Archive
        </MuiLink>
      </span>
    );
  } else if (color === theme.palette.warning) {
    statSection = (
      <span>
        Delayed until {finishedTime!.toLocaleTimeString()}
      </span>
    )
    infoSection = (
      <span>
        Retries Left: {4-job!.retry}
      </span>
    )
  }

  return (
    <Box sx={{ mb: 1.5 }}>
      <Paper sx={{ backgroundColor: color.main, color: color.contrastText }}>
        <Typography variant="body1" sx={{ p: 1 }}>
          {job ? (
            <MuiLink
              color="inherit"
              href={job.url}
              underline="hover"
              target="_blank"
              rel="noreferrer"
            >
              {job.url}
            </MuiLink>
          ) : (
            "No current job"
          )}
        </Typography>
        {job !== null && count === null && (
          <Box sx={{ width: "100%", px: 4, pb: 2 }}>
            <LinearProgress color="secondary" />
          </Box>
        )}
        {job !== null && (
          <Box sx={{ px: 2, pb: 1.5 }}>
            <span>Started at {new Date(job.created_at).toLocaleString()}{" | "}</span>
            {statSection}{statSection && " | "}
            {infoSection}{infoSection && " | "}
            {(job!.batches ?? []).map((batch) => (
              <span>
                <BatchChip batchId={batch} key={batch} />{" "}
              </span>
            ))}
          </Box>
        )}
      </Paper>
    </Box>
  );
}

function JobStatTable({
  stats,
}: {
  stats?: {
    r0: number;
    r1: number;
    r2: number;
    r3: number;
    r4: number;
    total: number;
  }
}) {
  const skeleton = <Skeleton variant="text" sx={{ fontSize: "1rem" }} />;
  return (
    <TableContainer component={Box} sx={{ maxWidth: 400 }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell># of Retries</TableCell>
            <TableCell># of Jobs</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          <TableRow>
            <TableCell>0</TableCell>
            <TableCell>{stats ? stats.r0 : skeleton}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell>1</TableCell>
            <TableCell>{stats ? stats.r1 : skeleton}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell>2</TableCell>
            <TableCell>{stats ? stats.r2 : skeleton}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell>3</TableCell>
            <TableCell>{stats ? stats.r3 : skeleton}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell>4</TableCell>
            <TableCell>{stats ? stats.r4 : skeleton}</TableCell>
          </TableRow>
        </TableBody>
      </Table>
      <div style={{ textAlign: "right", paddingRight: 20 }}>
        Total: {stats ? stats.total : inlineSkeleton}
      </div>
    </TableContainer>
  );
}

export default function Home() {
  const [startTime] = useState(new Date());
  const [loadCount, setLoadCount] = useState(0);
  const [currentJob, setCurrentJob] = useState<JobMaybe>(null);
  const [oldJob, setOldJob] = useState<JobMaybe>(null);
  const [oldJobCount, setOldJobCount] = useState(0);
  const [stats, setStats] = useState<Stats | null>(null);

  const setTitle = useContext(SetTitleContext);
  useEffect(() => {
    setTitle("Home");
  }, [setTitle]);
  

  useEffect(() => {
    Promise.all([
      GET("/current_job")
        .catch((error) => {
          console.error("Error getting current job", error);
          return { data: { job: null } };
        })
        .then(({ data }) => {
          const job: JobMaybe = data!.job;
          if ((job === null || currentJob === null) && job !== currentJob) {
            if (currentJob) {
              GET("/job/{job_id}", {
                params: { path: { job_id: currentJob.id } },
              }).then(({ data }) => {
                if (data) {
                  setOldJob(data);
                } else {
                  setOldJob(currentJob);
                }
                setOldJobCount(loadCount);
              });
            } else {
              setOldJob(currentJob);
              setOldJobCount(loadCount);
            }
          } else if (
            job !== null &&
            currentJob !== null &&
            job.id !== currentJob.id
          ) {
            GET("/job/{job_id}", {
              params: { path: { job_id: currentJob.id } },
            }).then(({ data }) => {
              if (data) {
                setOldJob(data);
              } else {
                setOldJob(currentJob);
              }
              setOldJobCount(loadCount);
            });
          }
          setCurrentJob(job);
        })
        .finally(() => {
          if (oldJob !== null && oldJobCount + 15 <= loadCount) {
            setOldJob(null);
            setOldJobCount(0);
          }
        }),
      GET("/stats").then(({ data }) => setStats(data!)),
    ]).finally(() => {
      setTimeout(() => setLoadCount(loadCount + 1), 1000);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- This is safe because loadCount is only set in this effect
  }, [loadCount]);



  return (
    <div>
      <p>
        This tool allows viewing the data in the server in a simple and
        non-painful way. Click on some of the links in the sidebar in order to
        go to the resource you are looking for.
      </p>
      <article>
        <h2>Current Job</h2>
        <JobBanner job={currentJob} startTime={startTime} />
        {oldJob !== null && (
          <>
            <JobBanner
              job={oldJob}
              startTime={startTime}
              count={oldJob && oldJobCount}
            />
          </>
        )}
      </article>
      <article>
        <h2>Statistics</h2>
        <Box sx={{ display: "flex", justifyContent: "center" }}>
          <Box sx={{ flex: "50%" }}>
            <ul>
              <li>
                Jobs:
                <ul>
                  <li>
                    Total Jobs: <InlineSkeletonDisplay>{stats?.jobs.total}</InlineSkeletonDisplay>
                  </li>
                  <li>
                    Failed Jobs: <InlineSkeletonDisplay>{stats?.jobs.failed}</InlineSkeletonDisplay>
                  </li>
                </ul>
              </li>
              <li>
                Batches: <InlineSkeletonDisplay>{stats?.batches}</InlineSkeletonDisplay>
              </li>
              <li>
                Repeat URLs:
                <ul>
                  <li>
                    Active:{" "}
                    <InlineSkeletonDisplay>{stats?.repeat_urls.active}</InlineSkeletonDisplay>
                  </li>
                  <li>
                    Inactive:{" "}
                    <InlineSkeletonDisplay>{stats?.repeat_urls.inactive}</InlineSkeletonDisplay>
                  </li>
                  <li>
                    Total: <InlineSkeletonDisplay>{stats?.repeat_urls.total}</InlineSkeletonDisplay>
                  </li>
                </ul>
              </li>
              <li>
                URLs:
                <ul>
                  <li>
                    Archived:
                    <ul>
                      <li>
                        Archived {"<="} 45 minutes ago:{" "}
                        <InlineSkeletonDisplay>{stats?.urls.super_recently_archived}</InlineSkeletonDisplay>
                      </li>
                      <li>
                        Archived {"<="} 4 hours ago:{" "}
                        <InlineSkeletonDisplay>{stats?.urls.recently_archived}</InlineSkeletonDisplay>
                      </li>
                      <li>
                        Archived {">"} 4 hours ago:{" "}
                        <InlineSkeletonDisplay>{stats?.urls.not_recently_archived}</InlineSkeletonDisplay>
                      </li>
                      <li>
                        Total:{" "}
                        <InlineSkeletonDisplay>{stats?.urls.total_archived}</InlineSkeletonDisplay>
                      </li>
                    </ul>
                  </li>
                  <li>
                    Not Archived:{" "}
                    <InlineSkeletonDisplay>{stats?.urls.not_archived}</InlineSkeletonDisplay>
                  </li>
                  <li>
                    Total: <InlineSkeletonDisplay>{stats?.urls.total}</InlineSkeletonDisplay>
                  </li>
                </ul>
              </li>
            </ul>
          </Box>
          <Box sx={{ flex: "50%" }}>
            <section>
              <h3>Jobs</h3>
              <section>
                <h4>In Progress</h4>
                <JobStatTable
                  stats={stats?.jobs.not_done}
                />
              </section>
              <section>
                <h4>Completed Jobs</h4>
                <JobStatTable
                  stats={stats?.jobs.completed}
                />
              </section>
            </section>
          </Box>
        </Box>
      </article>
    </div>
  );
}
