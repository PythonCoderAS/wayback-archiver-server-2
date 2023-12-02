import { PropsWithChildren } from "react";
import inlineSkeleton from "./inlineSkeleton";

export default function InlineSkeletonDisplay({ children }: PropsWithChildren) {
  console.log(children);
  return children !== null ? <b>{children}</b> : inlineSkeleton;
}
