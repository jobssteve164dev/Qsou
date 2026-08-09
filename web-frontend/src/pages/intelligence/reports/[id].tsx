import type { GetServerSideProps } from 'next';

export default function IntelligenceReportRedirectPage() {
  return null;
}

export const getServerSideProps: GetServerSideProps = async () => ({
  redirect: { destination: '/', permanent: false },
});
