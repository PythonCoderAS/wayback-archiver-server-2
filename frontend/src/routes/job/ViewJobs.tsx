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

export default function ViewJobs() {
  const retColDefs: [
    ColDef<Job, number>,
    ColDef<Job>,
    ColDef<Job, string | null>,
  ] = [
    {
      field: "retry",
      headerName: "Retries Used",
      sortable: true,
      filter: true,
    },
    {
      valueGetter: (params) => 4 - (params.data?.retry ?? 0),
      headerName: "Retries Left",
      sortable: true,
      filter: true,
    },
    {
      field: "delayed_until",
      headerName: "Delayed Until",
      sortable: true,
      filter: true,
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
    { field: "id", headerName: "ID", sortable: true, filter: true },
    { field: "url", headerName: "URL", sortable: true, filter: true },
    {
      field: "batches",
      headerName: "Batches",
      sortable: true,
      filter: true,
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
      filter: true,
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
    { field: "failed", headerName: "Failed At", sortable: true, filter: true },
    {
      headerName: "Retries",
      children: retColDefs,
    },
    {
      field: "created_at",
      headerName: "Created At",
      sortable: true,
      filter: true,
    },
    { field: "priority", headerName: "Priority", sortable: true, filter: true },
  ];

  return (
    <div className="ag-theme-quartz" style={{ height: "80vh" }}>
      <AgGridReact
        rowModelType="serverSide"
        columnDefs={colDefs}
        serverSideDatasource={{
          getRows(params: IServerSideGetRowsParams<Job>) {
            fetch("/job/grid_sort", {
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
