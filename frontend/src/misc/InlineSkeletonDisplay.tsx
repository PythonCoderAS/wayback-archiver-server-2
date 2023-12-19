import { PropsWithChildren } from "react";
import inlineSkeleton from "./inlineSkeleton";

export default function InlineSkeletonDisplay({ children }: PropsWithChildren) {
  return children !== null ? <b>{children}</b> : inlineSkeleton;
}
