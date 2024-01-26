import {
  ColDef,
  ColGroupDef,
  ICellRendererParams,
  IServerSideGetRowsParams,
  LoadSuccessParams,
} from "@ag-grid-community/core";
import { AgGridReact } from "@ag-grid-community/react";
import { DateTime } from "luxon";

import { Job } from "../../api/api";
import BatchChip from "../../misc/BatchChip";

export default function ViewJobs({ height = "80vh", url = "/job/grid_sort" }) {
  const retColDefs: [ColDef<Job, number>, ColDef<Job, string | null>] = [
    {
      field: "retry",
      headerName: "Retries Used",
      sortable: true,
      filter: "agMultiColumnFilter",
      filterParams: {
        filters: [
          {
            filter: "agNumberColumnFilter",
          },
          {
            filter: "agSetColumnFilter",
          },
        ],
      },
    },
    {
      field: "delayed_until",
      headerName: "Delayed Until",
      sortable: true,
      filter: "agMultiColumnFilter",
      filterParams: {
        filters: [
          {
            filter: "agDateColumnFilter",
          },
          {
            filter: "agSetColumnFilter",
          },
        ],
      },
    },
  ];
  const colDefs: [
    ColDef<Job, number>,
    ColDef<Job, string>,
    ColDef<Job, number[] | undefined>,
    ColDef<Job, string | null>,
    ColDef<Job, string | null>,
    ColGroupDef<Job>,
    ColDef<Job, string>,
    ColDef<Job, number>,
  ] = [
    {
      field: "id",
      headerName: "ID",
      sortable: true,
      filter: "agMultiColumnFilter",
      filterParams: {
        filters: [
          {
            filter: "agNumberColumnFilter",
          },
          {
            filter: "agSetColumnFilter",
          },
        ],
      },
    },
    {
      field: "url",
      headerName: "URL",
      sortable: true,
      filter: "agMultiColumnFilter",
      filterParams: {
        filters: [
          {
            filter: "agTextColumnFilter",
          },
          {
            filter: "agSetColumnFilter",
          },
        ],
      },
    },
    {
      field: "batches",
      headerName: "Batches",
      sortable: false,
      filter: "agMultiColumnFilter",
      filterParams: {
        filters: [
          {
            filter: "agNumberColumnFilter",
          },
          {
            filter: "agSetColumnFilter",
          },
        ],
      },
      cellRenderer(params: ICellRendererParams<Job, number[] | undefined>) {
        return (params.value ?? []).map((batchId) => (
          <>
            <BatchChip batchId={batchId} />
            <br />
          </>
        ));
      },
    },
    {
      field: "completed",
      headerName: "Archive URL",
      sortable: true,
      filter: "agMultiColumnFilter",
      filterParams: {
        filters: [
          {
            filter: "agDateColumnFilter",
          },
          {
            filter: "agSetColumnFilter",
          },
        ],
      },
      cellRenderer(params: ICellRendererParams<Job, string | null>) {
        if (params.value === null || params.value === undefined) {
          return null;
        }
        const date = DateTime.fromISO(params.value);
        const archiveURLString = `https://web.archive.org/web/${date.toFormat(
          "yyyyMMddHHmmss",
        )}/${params.data!.url}`;
        return <a href={archiveURLString}>{archiveURLString}</a>;
      },
    },
    {
      field: "failed",
      headerName: "Failed At",
      sortable: true,
      filter: "agMultiColumnFilter",
      filterParams: {
        filters: [
          {
            filter: "agDateColumnFilter",
          },
          {
            filter: "agSetColumnFilter",
          },
        ],
      },
    },
    {
      headerName: "Retries",
      children: retColDefs,
    },
    {
      field: "created_at",
      headerName: "Created At",
      sortable: true,
      filter: "agMultiColumnFilter",
      filterParams: {
        filters: [
          {
            filter: "agDateColumnFilter",
          },
          {
            filter: "agSetColumnFilter",
          },
        ],
      },
    },
    {
      field: "priority",
      headerName: "Priority",
      sortable: true,
      filter: "agMultiColumnFilter",
      filterParams: {
        filters: [
          {
            filter: "agNumberColumnFilter",
          },
          {
            filter: "agSetColumnFilter",
          },
        ],
      },
    },
  ];

  return (
    <div className="ag-theme-quartz" style={{ height }}>
      <AgGridReact
        rowModelType="serverSide"
        columnDefs={colDefs}
        serverSideDatasource={{
          getRows(params: IServerSideGetRowsParams<Job>) {
            fetch(url, {
              body: JSON.stringify(params.request),
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
            })
              .then((res) => res.json())
              .then((data: LoadSuccessParams) => params.success(data))
              .catch(() => params.fail());
          },
        }}
      />
    </div>
  );
}
