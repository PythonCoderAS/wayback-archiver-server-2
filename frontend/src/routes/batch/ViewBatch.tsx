import { Box, Link as MuiLink, createTheme } from "@mui/material";
import { useContext, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import Error404 from "../404";
import { SetTitleContext } from "../../AppFrame";
import { Batch, GET, RepeatURL } from "../../api/api";
import InlineSkeletonDisplay from "../../misc/InlineSkeletonDisplay";

const theme = createTheme();

export default function ViewBatch() {
  const { batchId } = useParams<{ batchId: string }>();

  const [counter, setCounter] = useState(0);
  const setTitle = useContext(SetTitleContext);

  const [batch, setBatch] = useState<Batch | null>(null);
  const [repeatURL] = useState<RepeatURL | null>(null);

  useEffect(() => {
    if (!batchId?.match(/^[1-9]\d*$/)) {
      return;
    }
    GET("/batch/{batch_id}", {
      params: { path: { batch_id: Number(batchId) } },
    })
      .then(({ data }) => {
        setBatch(data ?? null);
        if (data?.repeat_url && repeatURL === null) {
          // No-op
          // To-do: GET the repeat URL
        }
      })
      .finally(() => setTimeout(() => setCounter(counter + 1), 10000));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- This is a clock function
  }, [counter]);

  useEffect(() => {
    setTitle("Batch " + batchId);
  });
  if (!batchId?.match(/^[1-9]\d*$/)) {
    return <Error404 />;
  }

  return (
    <div>
      <section>
        <h2>Batch Info</h2>
        {batch?.repeat_url && (
          <Box
            sx={{ backgroundColor: theme.palette.primary.main }}
            color={theme.palette.primary.contrastText}
            px={2}
            py={0.5}
          >
            <p>
              This batch represents{" "}
              <MuiLink
                color="inherit"
                component={Link}
                to={`/repeat_url/${batch.repeat_url}`}
              >
                Repeat URL {batch.repeat_url}
              </MuiLink>{" "}
              <InlineSkeletonDisplay>
                {repeatURL && (
                  <MuiLink color="inherit" href={repeatURL.url.url}>
                    {repeatURL.url.url}
                  </MuiLink>
                )}
              </InlineSkeletonDisplay>
            </p>
          </Box>
        )}
        <p>
          Created at{" "}
          <InlineSkeletonDisplay>
            {batch?.created_at && new Date(batch.created_at).toLocaleString()}
          </InlineSkeletonDisplay>
        </p>
      </section>
      <section>
        <h2>Jobs</h2>
      </section>
    </div>
  );
}
