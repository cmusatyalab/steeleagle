---
sidebar_position: 3
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Python Package

SteelEagle provides a Python package, `steeleagle_sdk`, to make it easier to develop for and interact with SteelEagle modules through Python.
The package contains the following modules:
- [**api**](python/steeleagle_sdk/api): a Pydantic type-checked API for working with SteelEagle gRPC vehicle services
- [**dsl**](python/steeleage_sdk/dsl): a compiler for creating a finite state machine runnable mission from a SteelEagle DSL specification
- [**protocol**](python/steeleagle_sdk/protocol): low-level protocol bindings for gRPC and SteelEagle messages (only for advanced use-cases)
- [**tools**](python/steeleagle_sdk/tools): extra tools for facilitating development like auto-completion

To install `steeleagle_sdk`, it is strongly recommended that you use [uv](https://docs.astral.sh/uv/). If you prefer another package manager,
`steeleagle_sdk` can be installed like any PyPI package. SteelEagle requires Python >= 3.11.

<Tabs>
  <TabItem value="uv" label="uv" default>
    ```bash
    uv add steeleagle_sdk
    ```
  </TabItem>
  <TabItem value="pip" label="pip">
    ```bash
    pip install steeleagle_sdk
    ```
  </TabItem>
  <TabItem value="conda" label="conda">
    ```bash
    conda install steeleagle_sdk
    ```
  </TabItem>
</Tabs>

## Building from Source

To build from source, clone the [Github repo](https://github.com/cmusatyalab/steeleagle) or pull the dist from PyPI:

<Tabs groupId="build">
<TabItem value="clone" label="git clone" default>
```bash
git clone https://github.com/cmusatyalab/steeleagle
```
</TabItem>
<TabItem value="dist" label="dist">
```bash
pip download --no-deps --no-binary :all: steeleagle_sdk
```
</TabItem>
</Tabs>

Then, build using the following:

<Tabs groupId="build">
<TabItem value="clone" label="git clone" default>
```bash
cd steeleagle/sdk
uv build
```
</TabItem>
<TabItem value="dist" label="dist">
```bash
cd steeleagle_sdk
uv build
```
</TabItem>
</Tabs>
