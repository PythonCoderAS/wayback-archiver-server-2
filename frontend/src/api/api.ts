import createClient from "openapi-fetch";
import { paths, components } from "./schema"; // generated from openapi-typescript

const basePath = import.meta.env.PROD ? "/" : "http://localhost:8000/";

const client = createClient<paths>({ baseUrl: basePath });

export const { GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS, TRACE } = client;

export type Job = components["schemas"]["JobReturn"];
export type JobMaybe = Job | null;
export type Stats = components["schemas"]["Stats"];
export type Batch = components["schemas"]["BatchReturn"];
export type RepeatURL = components["schemas"]["RepeatURL"];

export interface Paginated<T> {
    data: T[];
    pagination: {
        current_page: number;
        total_pages: number;
        items: number;
    }
}

export type PaginatedJob = Paginated<Job>;