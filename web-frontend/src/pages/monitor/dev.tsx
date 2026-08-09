import type { GetServerSideProps } from 'next';

export default function DevelopmentConsoleRedirectPage() {
  return null;
}

export const getServerSideProps: GetServerSideProps = async () => ({
  redirect: { destination: '/data', permanent: false },
});
