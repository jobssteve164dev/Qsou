import type { GetServerSideProps } from 'next';

export default function MonitorRedirectPage() {
  return null;
}

export const getServerSideProps: GetServerSideProps = async () => ({
  redirect: { destination: '/data', permanent: false },
});
