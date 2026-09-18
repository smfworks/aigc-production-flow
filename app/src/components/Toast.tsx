type Props = {
  message: string | null;
};

export function Toast({ message }: Props) {
  return (
    <div className={message ? "toast is-on" : "toast"} role="status">
      {message}
    </div>
  );
}
