using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Ports;
using System.Linq;
using System.Management;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using System.Threading;

namespace UsbScreenProbe
{
    internal sealed class Device
    {
        public readonly string Port, Instance;
        public readonly int Health;
        public Device(string port, string instance, int health) { Port = port; Instance = instance; Health = health; }
    }

    internal sealed class PortSettings
    {
        public string Name;
        public readonly int Baud = 115200, DataBits = 8, WriteTimeout = 3000;
        public readonly Parity Parity = Parity.None;
        public readonly StopBits StopBits = StopBits.One;
        public readonly Handshake Handshake = Handshake.RequestToSend;
        public readonly bool Dtr = true;
    }

    internal interface IPort : IDisposable
    {
        void Open(PortSettings settings);
        void Write(byte[] data, int offset, int count);
        int Pending { get; }
    }
    internal interface IClock { long Milliseconds { get; } void Pause(); }
    internal sealed class Clock : IClock
    {
        private readonly Stopwatch timer = Stopwatch.StartNew();
        public long Milliseconds { get { return timer.ElapsedMilliseconds; } }
        public void Pause() { Thread.Sleep(20); }
    }
    internal sealed class NativePort : IPort
    {
        private SerialPort port;
        public void Open(PortSettings s)
        {
            port = new SerialPort(s.Name, s.Baud, s.Parity, s.DataBits, s.StopBits);
            port.Handshake = s.Handshake;
            port.DtrEnable = s.Dtr;
            port.WriteTimeout = s.WriteTimeout;
            port.Open();
        }
        public void Write(byte[] data, int offset, int count) { port.Write(data, offset, count); }
        public int Pending { get { return port.BytesToWrite; } }
        // Framework cleanup can block. This adapter is used only inside the owned worker.
        public void Dispose() { if (port != null) port.Dispose(); }
    }

    internal static class Probe
    {
        public const string Hash = "8cbbb7e39485e211548a4f3f448ca14eeb9358286e5eadf7079a324fdc97ed1d";
        public static readonly string Banner = "UsbScreenProbe 1.0.0" + Environment.NewLine;
        public static readonly string Help = "Usage: UsbScreenProbe.exe [--help | --list | --self-test | --port COMn]" + Environment.NewLine +
            "No arguments: choose a current COM port interactively. Sending requires typed SEND COMn." + Environment.NewLine +
            "90-second total worker budget includes input, inventory, transfer and cleanup. No retries." + Environment.NewLine;
        public const string ArgumentError = "E2: Invalid arguments. Use an explicit COM number (COM1 or higher).";
        public const string InventoryError = "E3: Serial inventory unavailable. Check Windows Device Manager and reconnect; do not install drivers or elevate for this probe.";
        public const string IdentityError = "E4: Port must uniquely match healthy USB VID 1A86/PID 5722/serial USB35INCHIPSV2. Run --list and check Device Manager.";
        public const string PatternError = "E5: Embedded pattern failed validation. Obtain a verified build; no port opened.";
        public const string TransferError = "E6: Transfer or cleanup failed; partial delivery is uncertain. Check the screen and close other serial applications before any new explicit run. No retry performed.";
        public const string Success = "307222 bytes drained to the serial output and port closed; not a rendering ACK. Photograph the screen. Check the device before another run.";
        public const string SelfTest = "PASS: embedded pattern and protocol: 122 writes, 307222 bytes; no USB opened.";
        private static readonly byte[] Orientation = { 0,0,0,0,0,121,100,1,64,1,224,0,0,0,0,0 };
        private static readonly byte[] Header = { 0,0,4,253,223,197 };

        public static bool ValidPort(string name) { return name != null && Regex.IsMatch(name, @"\ACOM[1-9][0-9]{0,8}\z"); }
        public static bool ValidArgs(string[] args)
        {
            return args.Length == 0 || (args.Length == 1 && new[] { "--help", "--list", "--self-test" }.Contains(args[0])) ||
                (args.Length == 2 && args[0] == "--port" && ValidPort(args[1]));
        }
        public static string IdentityLine(Device d)
        {
            return d.Port + " | " + d.Instance + " | health=" + d.Health + Environment.NewLine;
        }
        private static bool KnownIdentity(Device device)
        {
            return Regex.IsMatch(device.Instance ?? "", @"\AUSB\\VID_1A86&PID_5722\\USB35INCHIPSV2\z", RegexOptions.IgnoreCase);
        }
        private static Device Select(Device[] devices, string port)
        {
            if (!ValidPort(port)) throw new InvalidDataException();
            var matches = devices.Where(d => String.Equals(d.Port, port, StringComparison.OrdinalIgnoreCase)).ToArray();
            if (matches.Length != 1 || matches[0].Health != 0 || !ValidPort(matches[0].Port) ||
                !KnownIdentity(matches[0]) || devices.Count(KnownIdentity) != 1)
                throw new InvalidDataException();
            return matches[0];
        }
        public static Device[] Inventory()
        {
            var devices = new List<Device>();
            using (var search = new ManagementObjectSearcher("root\\cimv2", "SELECT DeviceID, PNPDeviceID, ConfigManagerErrorCode FROM Win32_SerialPort"))
            using (var results = search.Get())
                foreach (ManagementObject item in results)
                    using (item)
                        devices.Add(new Device(Convert.ToString(item["DeviceID"]), Convert.ToString(item["PNPDeviceID"]),
                            item["ConfigManagerErrorCode"] == null ? -1 : Convert.ToInt32(item["ConfigManagerErrorCode"])));
            return devices.ToArray();
        }
        public static byte[] LoadPattern()
        {
            using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("pattern.rgb565"))
            {
                if (stream == null) return new byte[0];
                using (var buffer = new MemoryStream()) { stream.CopyTo(buffer); return buffer.ToArray(); }
            }
        }
        private static bool ValidPattern(byte[] payload)
        {
            if (payload == null || payload.Length != 307200) return false;
            using (var sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(payload)).Replace("-", "").ToLowerInvariant() == Hash;
        }
        // One protocol implementation for real sending, the public self-test and tests.
        public static void Send(byte[] payload, Action<byte[], int, int> write)
        {
            write(Orientation, 0, Orientation.Length);
            write(Header, 0, Header.Length);
            for (int offset = 0; offset < payload.Length; offset += 2560) write(payload, offset, 2560);
        }
        public static int Run(string[] args, TextReader input, TextWriter output, TextWriter error,
                              Func<Device[]> inventory, Func<IPort> createPort, IClock clock, byte[] payload)
        {
            if (!ValidArgs(args)) { error.WriteLine(ArgumentError); error.Write(Help); return 2; }
            output.Write(Banner);
            if (args.Length == 1 && args[0] == "--help") { output.Write(Help); return 0; }
            if (!ValidPattern(payload)) { error.WriteLine(PatternError); return 5; }
            if (args.Length == 1 && args[0] == "--self-test")
            {
                int writes = 0, bytes = 0;
                Send(payload, delegate(byte[] data, int offset, int count) { writes++; bytes += count; });
                if (writes != 122 || bytes != 307222) { error.WriteLine(PatternError); return 5; }
                output.WriteLine(SelfTest);
                return 0;
            }
            Device[] devices;
            try { devices = inventory(); }
            catch { error.WriteLine(InventoryError); return 3; }
            bool list = args.Length == 1 && args[0] == "--list";
            if (list || args.Length == 0)
            {
                foreach (Device d in devices) output.Write(IdentityLine(d));
                if (devices.Length == 0) output.WriteLine("No serial ports reported by WMI.");
                if (list) return 0;
                output.Write("Choose COMn (Enter cancels): ");
            }
            string name = args.Length == 0 ? input.ReadLine() : args[1];
            if (String.IsNullOrEmpty(name)) { output.WriteLine("Cancelled; no port opened."); return 0; }
            Device selected;
            try { selected = Select(devices, name); }
            catch { error.WriteLine(IdentityError); return 4; }
            output.Write(IdentityLine(selected));
            output.Write("Type SEND " + name + " to send one image: ");
            if (input.ReadLine() != "SEND " + name) { output.WriteLine("Cancelled; no port opened."); return 0; }
            try { devices = inventory(); }
            catch { error.WriteLine(InventoryError); return 3; }
            try { Select(devices, name); }
            catch { error.WriteLine(IdentityError); return 4; }
            IPort port = null;
            bool failed = false;
            try
            {
                port = createPort();
                port.Open(new PortSettings { Name = name });
                Send(payload, port.Write);
                long start = clock.Milliseconds;
                while (port.Pending != 0)
                {
                    if (clock.Milliseconds - start >= 15000) throw new TimeoutException();
                    clock.Pause();
                }
            }
            catch { failed = true; }
            finally
            {
                // Never let cleanup erase the primary failure or emit premature success.
                if (port != null) try { port.Dispose(); } catch { failed = true; }
            }
            if (failed) { error.WriteLine(TransferError); return 6; }
            output.WriteLine(Success);
            return 0;
        }
    }

    internal interface IOwnChild : IDisposable
    {
        bool Wait(int milliseconds);
        int ExitCode { get; }
        void Kill();
    }
    internal sealed class OwnedChild : IOwnChild
    {
        private readonly Process process;
        private readonly IntPtr job;
        private readonly EventWaitHandle gate;
        private OwnedChild(Process process, IntPtr job, EventWaitHandle gate)
        {
            this.process = process;
            this.job = job;
            this.gate = gate;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct BasicLimits
        {
            public long ProcessTime, JobTime;
            public uint Flags;
            public UIntPtr Minimum, Maximum;
            public uint ActiveProcesses;
            public UIntPtr Affinity;
            public uint Priority, Scheduling;
        }
        [StructLayout(LayoutKind.Sequential)]
        private struct IoCounters { public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes; }
        [StructLayout(LayoutKind.Sequential)]
        private struct ExtendedLimits
        {
            public BasicLimits Basic;
            public IoCounters Io;
            public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
        }
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr CreateJobObject(IntPtr attributes, string name);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool SetInformationJobObject(IntPtr job, int infoClass, ref ExtendedLimits limits, uint length);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
        [DllImport("kernel32.dll")]
        private static extern bool CloseHandle(IntPtr handle);
        public static OwnedChild Start(string executable, string arguments, string marker)
        {
            var start = new ProcessStartInfo(executable, arguments) { UseShellExecute = false };
            // Inherit all console handles: redirected CI input works without a relay or output deadlock.
            if (marker != null) start.EnvironmentVariables[Program.MarkerVariable] = marker;
            IntPtr job = CreateJobObject(IntPtr.Zero, null);
            if (job == IntPtr.Zero) throw new IOException("Cannot create owned worker job.");
            Process process = null;
            EventWaitHandle gate = null;
            try
            {
                // A worker cannot begin inventory/input until lifetime containment is installed.
                if (marker != null)
                    gate = new EventWaitHandle(false, EventResetMode.ManualReset, "Local\\UsbScreenProbe-" + marker);
                var limits = new ExtendedLimits();
                limits.Basic.Flags = 0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                if (!SetInformationJobObject(job, 9, ref limits, (uint)Marshal.SizeOf(typeof(ExtendedLimits))))
                    throw new IOException("Cannot bound owned worker lifetime.");
                process = Process.Start(start);
                if (!AssignProcessToJobObject(job, process.Handle) && !process.HasExited)
                    throw new IOException("Cannot attach owned worker to lifetime job.");
                if (gate != null) gate.Set();
                return new OwnedChild(process, job, gate);
            }
            catch
            {
                if (process != null)
                {
                    try { process.Kill(); } catch { }
                    try { process.WaitForExit(2000); } catch { }
                    process.Dispose();
                }
                CloseHandle(job);
                if (gate != null) gate.Dispose();
                throw;
            }
        }
        public bool Wait(int milliseconds) { return process.WaitForExit(milliseconds); }
        public int ExitCode { get { return process.ExitCode; } }
        public void Kill() { process.Kill(); }
        public void Dispose()
        {
            CloseHandle(job);
            if (gate != null) gate.Dispose();
            process.Dispose();
        }
    }
    internal static class Supervisor
    {
        public const string TimeoutMessage = "E8: Worker timed out and was stopped; partial delivery is uncertain. Check the screen. No retry performed.";
        public const string UncertainMessage = "E8: Worker termination could not be confirmed; partial delivery is uncertain. Do not rerun; close this probe and check Task Manager and the screen.";
        public static int Wait(IOwnChild child, int budget, TextWriter error)
        {
            try { if (child.Wait(budget)) return child.ExitCode; }
            catch { /* A broken wait still requires owned-child cleanup. */ }
            try { child.Kill(); } catch { /* It may have exited concurrently; verify below. */ }
            bool reaped = false;
            try { reaped = child.Wait(2000); } catch { }
            error.WriteLine(reaped ? TimeoutMessage : UncertainMessage);
            return 8;
        }
    }
}
