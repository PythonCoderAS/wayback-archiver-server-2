import createClient from "openapi-fetch";
import { paths } from "./schema"; // generated from openapi-typescript

const basePath = import.meta.env.PROD ? "/" : "http://localhost:8000/";

const client = createClient<paths>({ baseUrl: basePath });

export const { GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS, TRACE } = client;

export type JobMaybe = paths["/current_job"]["get"]["responses"]["200"]["content"]["application/json"]["job"];
export type Job = NonNullable<JobMaybe>;