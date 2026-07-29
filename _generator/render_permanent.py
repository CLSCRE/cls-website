#!/usr/bin/env python
"""Backward-compatible targeted renderer for the Permanent Loans hub."""

from render_financing_hubs import render_hubs


if __name__ == "__main__":
    render_hubs(slugs=["permanent-loans"], write=True)
