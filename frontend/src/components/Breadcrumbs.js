// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

import React from 'react';
import BreadcrumbGroup from '@cloudscape-design/components/breadcrumb-group';
import { useLocation, useNavigate } from 'react-router-dom';

export const Breadcrumbs = React.memo(() => {
  const location = useLocation();
  const navigate = useNavigate();

  function getBreadcrumbs(pathname) {
    const baseBreadcrumb = { text: 'Home', href: '/dashboard' };

    const routes = {
      '/dashboard': [baseBreadcrumb],
      '/upload': [baseBreadcrumb, { text: 'Upload Files', href: '/upload' }],
      '/jobs': [baseBreadcrumb, { text: 'Jobs', href: '/jobs' }],
      '/review': [baseBreadcrumb, { text: 'Review Queue', href: '/review' }],
      '/settings': [baseBreadcrumb, { text: 'Settings', href: '/settings' }]
    };

    // Handle job details route
    if (pathname.startsWith('/jobs/')) {
      return [
        baseBreadcrumb,
        { text: 'Jobs', href: '/jobs' },
        { text: 'Job Details', href: pathname }
      ];
    }

    return routes[pathname] || [baseBreadcrumb];
  }

  const breadcrumbs = getBreadcrumbs(location.pathname);

  return (
    <BreadcrumbGroup
      items={breadcrumbs}
      expandAriaLabel="Show path"
      ariaLabel="Breadcrumbs"
      onFollow={(event) => {
        if (!event.detail.external) {
          event.preventDefault();
          navigate(event.detail.href);
        }
      }}
    />
  );
});